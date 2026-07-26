"""Runtime scheduler for Energy Appliance Scheduler."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
)
from homeassistant.helpers.script import Script
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ALEXA_TEXT_KEYS,
    CONF_ALEXA_MEDIA_PLAYERS,
    CONF_ALEXA_MESSAGE_TYPE,
    CONF_ALEXA_QUIET_HOURS_ENABLED,
    CONF_ALEXA_QUIET_HOURS_END,
    CONF_ALEXA_QUIET_HOURS_START,
    CONF_ALEXA_VOLUME_PERCENT,
    CONF_FAVORABLE_NOW_SENSOR,
    CONF_FAVORABLE_PHASE_SENSOR,
    CONF_ICON,
    CONF_OPERATING_STATE_ENTITY,
    CONF_PREPARE_ACTIONS,
    CONF_PRICE_SENSOR,
    CONF_PROGRAM_BEHAVIOR,
    CONF_PROGRAM_ENTITY,
    CONF_RUNNING_STATES,
    CONF_START_ACTIONS,
    CONF_START_CONFIRMATION_TIMEOUT,
    DEFAULT_ALEXA_MESSAGE_TYPE,
    DEFAULT_ALEXA_QUIET_HOURS_ENABLED,
    DEFAULT_ALEXA_QUIET_HOURS_END,
    DEFAULT_ALEXA_QUIET_HOURS_START,
    DEFAULT_ALEXA_VOLUME_PERCENT,
    DEFAULT_ALEXA_TEXTS_DE,
    DEFAULT_ALEXA_TEXTS_EN,
    DEFAULT_ICON,
    DEFAULT_MODE,
    DEFAULT_PROGRAM_BEHAVIOR,
    DEFAULT_RUNNING_STATES,
    DEFAULT_START_CONFIRMATION_TIMEOUT,
    MAX_ALEXA_VOLUME_PERCENT,
    MIN_ALEXA_VOLUME_PERCENT,
    DOMAIN,
    MODE_FIXED_TIME,
    MODE_NEXT_FAVORABLE,
    PROGRAM_BEHAVIOR_SELECT_STARTS_DEVICE,
    SAVE_DELAY_SECONDS,
    START_MODES,
    STATUS_CANCELLED,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_OPTIONS,
    STATUS_SCHEDULED,
    STATUS_STARTED,
    STATUS_STARTING,
    STATUS_START_UNCONFIRMED,
    STATUS_WAITING_CONFIRMATION,
    STATUS_WAITING_DATA,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .messages import render_message_template
from .price import (
    collect_price_slots,
    current_state_price,
    favorable_window,
    parse_datetime,
    price_at,
)

_LOGGER = logging.getLogger(__name__)


class SchedulerError(HomeAssistantError):
    """Base scheduler error."""


class MissingScheduleError(SchedulerError):
    """Raised when no valid start time can be calculated."""


class PriceUnavailableError(SchedulerError):
    """Raised when no electricity price is available for the requested start."""


def _friendly_start_error(error: Exception) -> str:
    """Return a concise user-facing German message for known start failures."""
    raw_message = str(error).strip()
    normalized = raw_message.casefold()

    if (
        "sdk.error.programnotwritable" in normalized
        or "program can currently not be written" in normalized
    ):
        return (
            "Home Connect hat den Programmstart abgelehnt, weil das ausgewählte "
            "Programm momentan nicht gestartet werden kann. Prüfe, ob das Gerät "
            "eingeschaltet und online ist, die Tür vollständig geschlossen ist, "
            "Fernstart beziehungsweise Fernbedienung am Gerät aktiviert ist und "
            "kein anderes Programm läuft."
        )

    if (
        "sdk.error.homeappliance.connection.initialization.failed" in normalized
        or "homeappliance is offline" in normalized
    ):
        return (
            "Das Home-Connect-Gerät ist derzeit nicht erreichbar oder offline. "
            "Prüfe die Stromversorgung, WLAN-Verbindung und den Gerätestatus."
        )

    if "remotecontrolnotactive" in normalized or "remote control is not active" in normalized:
        return (
            "Der Fernstart beziehungsweise die Fernbedienung ist am Gerät nicht "
            "aktiviert. Aktiviere die Funktion direkt am Gerät und versuche es erneut."
        )

    return raw_message or error.__class__.__name__


@dataclass(slots=True)
class AppliancePersistentState:
    """Persistent per-appliance runtime state."""

    mode: str = DEFAULT_MODE
    scheduled_time: str | None = None
    selected_program: str | None = None
    armed: bool = False
    alexa_quiet_hours_override: bool = False
    planned_start: str | None = None
    planned_price_cents: float | None = None
    status: str = STATUS_IDLE
    last_started: str | None = None
    last_started_price_cents: float | None = None
    last_error: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "AppliancePersistentState":
        """Create state from stored data with safe defaults."""
        if not isinstance(data, Mapping):
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        state = cls(**{key: value for key, value in data.items() if key in allowed})
        if state.mode not in START_MODES:
            state.mode = DEFAULT_MODE
        if state.status not in STATUS_OPTIONS:
            state.status = STATUS_IDLE
        return state


class SchedulerRuntime:
    """Runtime shared by all appliance subentries."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.managers: dict[str, ApplianceManager] = {}
        self._stored: dict[str, Any] = {}
        self._unsub_sources: Callable[[], None] | None = None

    @property
    def is_german(self) -> bool:
        return str(getattr(self.hass.config, "language", "en") or "en").lower().startswith("de")

    def setting(self, key: str, default: Any = None) -> Any:
        """Return an option override or the original config-entry value."""
        return self.entry.options.get(key, self.entry.data.get(key, default))

    @property
    def favorable_phase_sensor(self) -> str:
        return str(self.setting(CONF_FAVORABLE_PHASE_SENSOR))

    @property
    def favorable_now_sensor(self) -> str:
        return str(self.setting(CONF_FAVORABLE_NOW_SENSOR))

    @property
    def price_sensor(self) -> str:
        return str(self.setting(CONF_PRICE_SENSOR))

    @property
    def alexa_media_players(self) -> list[str]:
        value = self.setting(CONF_ALEXA_MEDIA_PLAYERS, [])
        return list(value) if isinstance(value, list) else [str(value)] if value else []

    @property
    def alexa_message_type(self) -> str:
        return str(self.setting(CONF_ALEXA_MESSAGE_TYPE, DEFAULT_ALEXA_MESSAGE_TYPE))

    @property
    def alexa_quiet_hours_enabled(self) -> bool:
        return bool(
            self.setting(
                CONF_ALEXA_QUIET_HOURS_ENABLED,
                DEFAULT_ALEXA_QUIET_HOURS_ENABLED,
            )
        )

    @staticmethod
    def _time_setting(value: Any, default: str) -> dt_time:
        if isinstance(value, dt_time):
            return value.replace(microsecond=0, tzinfo=None)
        try:
            return dt_time.fromisoformat(str(value or default)).replace(
                microsecond=0, tzinfo=None
            )
        except ValueError:
            return dt_time.fromisoformat(default)

    @property
    def alexa_quiet_hours_start(self) -> dt_time:
        return self._time_setting(
            self.setting(
                CONF_ALEXA_QUIET_HOURS_START,
                DEFAULT_ALEXA_QUIET_HOURS_START,
            ),
            DEFAULT_ALEXA_QUIET_HOURS_START,
        )

    @property
    def alexa_quiet_hours_end(self) -> dt_time:
        return self._time_setting(
            self.setting(
                CONF_ALEXA_QUIET_HOURS_END,
                DEFAULT_ALEXA_QUIET_HOURS_END,
            ),
            DEFAULT_ALEXA_QUIET_HOURS_END,
        )

    @property
    def alexa_volume_percent(self) -> int:
        try:
            value = int(
                round(
                    float(
                        self.setting(
                            CONF_ALEXA_VOLUME_PERCENT,
                            DEFAULT_ALEXA_VOLUME_PERCENT,
                        )
                    )
                )
            )
        except (TypeError, ValueError):
            value = DEFAULT_ALEXA_VOLUME_PERCENT
        return max(
            MIN_ALEXA_VOLUME_PERCENT,
            min(MAX_ALEXA_VOLUME_PERCENT, value),
        )

    def is_alexa_quiet_time(self, moment: datetime | None = None) -> bool:
        """Return whether Alexa speech is currently suppressed."""
        if not self.alexa_quiet_hours_enabled:
            return False
        start = self.alexa_quiet_hours_start
        end = self.alexa_quiet_hours_end
        if start == end:
            return False
        current = (moment or dt_util.now()).timetz().replace(tzinfo=None)
        if start < end:
            return start <= current < end
        return current >= start or current < end

    def alexa_template(self, key: str) -> str:
        defaults = DEFAULT_ALEXA_TEXTS_DE if self.is_german else DEFAULT_ALEXA_TEXTS_EN
        return str(self.setting(key, defaults[key]))

    async def async_setup(self) -> None:
        """Load persistent state and build appliance managers."""
        loaded = await self.store.async_load()
        self._stored = loaded if isinstance(loaded, dict) else {}
        appliance_states = self._stored.get("appliances", {})
        if not isinstance(appliance_states, Mapping):
            appliance_states = {}

        for subentry in self.entry.subentries.values():
            manager = ApplianceManager(
                self,
                subentry,
                AppliancePersistentState.from_dict(appliance_states.get(subentry.subentry_id)),
            )
            manager.normalize_selected_program()
            self.managers[subentry.subentry_id] = manager

        source_entities = {
            self.favorable_phase_sensor,
            self.favorable_now_sensor,
            self.price_sensor,
        }
        for manager in self.managers.values():
            source_entities.update(manager.source_entities)
        source_entities.discard("")
        self._unsub_sources = async_track_state_change_event(
            self.hass,
            list(source_entities),
            self._source_changed,
        )

        _LOGGER.info(
            "Energy Appliance Scheduler loaded with %d appliance(s); "
            "favorable phase sensor=%s, favorable-now sensor=%s, price sensor=%s, "
            "Alexa target count=%d, Alexa volume=%d%%, quiet hours=%s (%s-%s)",
            len(self.managers),
            self.favorable_phase_sensor,
            self.favorable_now_sensor,
            self.price_sensor,
            len(self.alexa_media_players),
            self.alexa_volume_percent,
            "enabled" if self.alexa_quiet_hours_enabled else "disabled",
            self.alexa_quiet_hours_start.isoformat(timespec="minutes"),
            self.alexa_quiet_hours_end.isoformat(timespec="minutes"),
        )
        for manager in self.managers.values():
            _LOGGER.info(
                "Appliance %s loaded: program entity=%s, operating-state entity=%s, "
                "Alexa quiet-hours override=%s",
                manager.name,
                manager.program_entity or "not configured",
                manager.operating_state_entity or "not configured",
                "enabled" if manager.alexa_quiet_hours_override else "disabled",
            )
            await manager.async_restore_schedule()
        self.schedule_save()

    async def async_unload(self) -> None:
        """Unload listeners, timers and scripts."""
        if self._unsub_sources is not None:
            self._unsub_sources()
            self._unsub_sources = None
        await self.store.async_save(self._serialize())
        for manager in self.managers.values():
            await manager.async_unload()
        _LOGGER.info("Energy Appliance Scheduler unloaded")

    @callback
    def _source_changed(self, event: Event) -> None:
        """Refresh entity state and recalculate armed schedules."""
        entity_id = str(event.data.get("entity_id", ""))
        esc_source = entity_id in {
            self.favorable_phase_sensor,
            self.favorable_now_sensor,
            self.price_sensor,
        }
        for manager in self.managers.values():
            if entity_id in manager.source_entities:
                manager.normalize_selected_program()
                manager.notify_updated()
            # Fixed-time starts are independent of ESC source updates. Only
            # favorable-phase schedules are recalculated when ESC entities change.
            if (
                esc_source
                and manager.state.armed
                and not manager.executing
                and manager.state.mode == MODE_NEXT_FAVORABLE
            ):
                self.hass.async_create_task(manager.async_handle_source_update())

    @callback
    def schedule_save(self) -> None:
        """Schedule persistent state storage."""
        self.store.async_delay_save(self._serialize, SAVE_DELAY_SECONDS)

    @callback
    def _serialize(self) -> dict[str, Any]:
        return {
            "appliances": {
                subentry_id: asdict(manager.state)
                for subentry_id, manager in self.managers.items()
            }
        }

    def is_favorable_now(self) -> bool:
        state = self.hass.states.get(self.favorable_now_sensor)
        return state is not None and state.state == "on"

    def price_for(self, moment: datetime) -> float | None:
        """Find the EUR/kWh price applying at a requested timestamp."""
        price_state = self.hass.states.get(self.price_sensor)
        favorable_state = self.hass.states.get(self.favorable_phase_sensor)
        attribute_sets: list[Mapping[str, Any]] = []
        if price_state is not None:
            attribute_sets.append(price_state.attributes)
        if favorable_state is not None:
            attribute_sets.append(favorable_state.attributes)

        price = price_at(collect_price_slots(*attribute_sets), moment)
        if price is not None:
            return price

        now = dt_util.now()
        if price_state is not None and abs((moment - now).total_seconds()) <= 30 * 60:
            return current_state_price(price_state.state)
        return None

    def current_price(self) -> float | None:
        """Return the numeric state of the configured current-price sensor."""
        price_state = self.hass.states.get(self.price_sensor)
        if price_state is None:
            return None
        return current_state_price(price_state.state)

    def next_favorable_start(self) -> datetime | None:
        """Return an immediate current start or the next favorable phase."""
        now = dt_util.now()
        if self.is_favorable_now():
            return now + timedelta(seconds=2)

        phase_state = self.hass.states.get(self.favorable_phase_sensor)
        if phase_state is None:
            return None
        window = favorable_window(phase_state.attributes)
        if window is not None:
            start, end = window
            if start >= now:
                return start
            if now - start <= timedelta(seconds=60) and (end is None or end > now):
                return now + timedelta(seconds=2)

        future_starts: list[datetime] = []
        blocks = phase_state.attributes.get("all_favorable_blocks", [])
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, Mapping):
                    continue
                block_start = parse_datetime(block.get("favorable_from"))
                if block_start is not None and block_start >= now:
                    future_starts.append(block_start)
        if future_starts:
            return min(future_starts)

        state_time = parse_datetime(phase_state.state)
        return state_time if state_time and state_time >= now else None

    async def async_announce(
        self,
        message: str,
        *,
        level: int = logging.INFO,
        quiet_hours_override: bool = False,
    ) -> None:
        """Log a user-facing message and optionally speak it on Alexa devices."""
        if not message:
            return

        # Every user-facing integration message is written to the Home Assistant log,
        # even when no Alexa target is configured or Alexa is unavailable.
        _LOGGER.log(level, "%s", message)

        targets = self.alexa_media_players
        if not targets:
            _LOGGER.debug(
                "Alexa output skipped because no Alexa media player is configured"
            )
            return
        quiet_time = self.is_alexa_quiet_time()
        if quiet_time and not quiet_hours_override:
            _LOGGER.info(
                "Alexa output suppressed during quiet hours %s-%s; message remains "
                "available in the Home Assistant log",
                self.alexa_quiet_hours_start.isoformat(timespec="minutes"),
                self.alexa_quiet_hours_end.isoformat(timespec="minutes"),
            )
            return
        if quiet_time and quiet_hours_override:
            _LOGGER.info(
                "Alexa quiet hours %s-%s overridden for this appliance; message will "
                "be announced",
                self.alexa_quiet_hours_start.isoformat(timespec="minutes"),
                self.alexa_quiet_hours_end.isoformat(timespec="minutes"),
            )
        if not self.hass.services.has_service("notify", "alexa_media"):
            _LOGGER.error("Alexa Media Player service notify.alexa_media is unavailable")
            return

        await self._async_set_alexa_volume(targets)
        try:
            await self.hass.services.async_call(
                "notify",
                "alexa_media",
                {
                    "message": message,
                    "target": targets,
                    "data": {"type": self.alexa_message_type},
                },
                blocking=True,
            )
            _LOGGER.debug("Alexa message delivered to %s", ", ".join(targets))
        except Exception:
            _LOGGER.exception("Alexa announcement failed: %s", message)

    async def _async_set_alexa_volume(self, targets: list[str]) -> None:
        """Set the configured output volume before sending an Alexa message."""
        if not self.hass.services.has_service("media_player", "volume_set"):
            _LOGGER.warning(
                "Alexa volume could not be set because media_player.volume_set is "
                "unavailable"
            )
            return

        volume_level = self.alexa_volume_percent / 100.0
        successful_targets = 0
        for target in targets:
            state = self.hass.states.get(target)
            if state is None:
                _LOGGER.warning(
                    "Alexa volume was not set because target %s does not exist",
                    target,
                )
                continue
            if state.state == STATE_UNAVAILABLE:
                _LOGGER.warning(
                    "Alexa volume was not set because target %s is unavailable",
                    target,
                )
                continue
            try:
                await self.hass.services.async_call(
                    "media_player",
                    "volume_set",
                    {
                        "entity_id": target,
                        "volume_level": volume_level,
                    },
                    blocking=True,
                )
                successful_targets += 1
            except Exception:
                _LOGGER.exception(
                    "Setting Alexa volume to %d%% failed for %s",
                    self.alexa_volume_percent,
                    target,
                )
        _LOGGER.debug(
            "Alexa volume set to %d%% for %d of %d configured targets",
            self.alexa_volume_percent,
            successful_targets,
            len(targets),
        )


class ApplianceManager:
    """Manage one appliance subentry and its one-shot scheduled start."""

    def __init__(
        self,
        runtime: SchedulerRuntime,
        subentry: ConfigSubentry,
        state: AppliancePersistentState,
    ) -> None:
        self.runtime = runtime
        self.hass = runtime.hass
        self.subentry = subentry
        self.state = state
        self._listeners: set[Callable[[], None]] = set()
        self._unsub_timer: Callable[[], None] | None = None
        self._executing = False
        self._replan_lock = asyncio.Lock()
        self._execution_lock = asyncio.Lock()
        self._last_logged_state: tuple[Any, ...] | None = None
        self._prepare_script = self._make_script(
            subentry.data.get(CONF_PREPARE_ACTIONS, []), "prepare"
        )
        self._start_script = self._make_script(
            subentry.data.get(CONF_START_ACTIONS, []), "start"
        )

    @property
    def name(self) -> str:
        return self.subentry.title

    @property
    def icon(self) -> str:
        return str(self.subentry.data.get(CONF_ICON) or DEFAULT_ICON)

    @property
    def executing(self) -> bool:
        return self._executing

    @property
    def alexa_quiet_hours_override(self) -> bool:
        """Return whether this appliance may announce during global quiet hours."""
        return self.state.alexa_quiet_hours_override

    async def async_set_alexa_quiet_hours_override(self, enabled: bool) -> None:
        """Enable or disable the per-appliance Alexa quiet-hours override."""
        enabled = bool(enabled)
        if self.state.alexa_quiet_hours_override == enabled:
            return
        self.state.alexa_quiet_hours_override = enabled
        _LOGGER.info(
            "Appliance %s Alexa quiet-hours override %s",
            self.name,
            "enabled" if enabled else "disabled",
        )
        self.notify_updated()

    @property
    def scheduled_time(self) -> datetime | None:
        return parse_datetime(self.state.scheduled_time)

    @property
    def planned_start(self) -> datetime | None:
        return parse_datetime(self.state.planned_start)

    @property
    def program_entity(self) -> str | None:
        value = self.subentry.data.get(CONF_PROGRAM_ENTITY)
        return str(value) if value else None

    @property
    def program_behavior(self) -> str:
        return str(self.subentry.data.get(CONF_PROGRAM_BEHAVIOR, DEFAULT_PROGRAM_BEHAVIOR))

    @property
    def operating_state_entity(self) -> str | None:
        value = self.subentry.data.get(CONF_OPERATING_STATE_ENTITY)
        return str(value) if value else None

    @property
    def running_states(self) -> set[str]:
        raw = str(self.subentry.data.get(CONF_RUNNING_STATES, DEFAULT_RUNNING_STATES) or "")
        return {item.strip().casefold() for item in raw.split(",") if item.strip()}

    @property
    def confirmation_timeout(self) -> int:
        try:
            return int(
                self.subentry.data.get(
                    CONF_START_CONFIRMATION_TIMEOUT,
                    DEFAULT_START_CONFIRMATION_TIMEOUT,
                )
            )
        except (TypeError, ValueError):
            return DEFAULT_START_CONFIRMATION_TIMEOUT

    @property
    def source_entities(self) -> set[str]:
        return {entity for entity in (self.program_entity, self.operating_state_entity) if entity}

    @property
    def program_options(self) -> list[str]:
        if not self.program_entity:
            return []
        state = self.hass.states.get(self.program_entity)
        if state is None:
            return []
        options = state.attributes.get("options", [])
        return [str(option) for option in options] if isinstance(options, list) else []

    def normalize_selected_program(self) -> None:
        """Keep the persisted program valid when the source options change."""
        if not self.program_entity:
            self.state.selected_program = None
            return
        options = self.program_options
        if not options:
            return
        if self.state.selected_program in options:
            return
        source_state = self.hass.states.get(self.program_entity)
        if source_state is not None and source_state.state in options:
            self.state.selected_program = source_state.state
        else:
            self.state.selected_program = options[0]

    def _make_script(self, actions: list[dict[str, Any]], suffix: str) -> Script | None:
        if not actions:
            return None
        return Script(self.hass, actions, f"{self.name}: {suffix}", DOMAIN)

    @callback
    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def notify_updated(self) -> None:
        self._log_state_if_changed()
        self.runtime.schedule_save()
        for listener in tuple(self._listeners):
            listener()

    def _log_state_if_changed(self) -> None:
        """Log meaningful appliance state changes without duplicate log entries."""
        snapshot = (
            self.state.status,
            self.state.armed,
            self.state.alexa_quiet_hours_override,
            self.state.mode,
            self.state.planned_start,
            self.state.planned_price_cents,
            self.state.selected_program,
            self.state.last_error,
        )
        if snapshot == self._last_logged_state:
            return
        self._last_logged_state = snapshot

        level = logging.INFO
        if self.state.status == STATUS_ERROR:
            level = logging.ERROR
        elif self.state.status in (STATUS_START_UNCONFIRMED, STATUS_WAITING_DATA):
            level = logging.WARNING

        price = (
            f"{self.state.planned_price_cents:.6f} ct/kWh"
            if self.state.planned_price_cents is not None
            else "not planned"
        )
        _LOGGER.log(
            level,
            "Appliance %s state changed: status=%s, start permission=%s, "
            "Alexa quiet-hours override=%s, mode=%s, planned start=%s, "
            "planned price=%s, program=%s, error=%s",
            self.name,
            self.state.status,
            "enabled" if self.state.armed else "disabled",
            "enabled" if self.state.alexa_quiet_hours_override else "disabled",
            self.state.mode,
            self.state.planned_start or "not planned",
            price,
            self.state.selected_program or "not selected",
            self.state.last_error or "none",
        )

    @callback
    def cancel_timer(self) -> None:
        if self._unsub_timer is not None:
            self._unsub_timer()
            self._unsub_timer = None

    async def async_unload(self) -> None:
        self.cancel_timer()
        for script in (self._prepare_script, self._start_script):
            if script is None:
                continue
            async_unload = getattr(script, "async_unload", None)
            if async_unload is not None:
                await async_unload()

    async def async_restore_schedule(self) -> None:
        """Recreate a persisted one-shot timer after Home Assistant restarts."""
        if not self.state.armed:
            return
        planned = self.planned_start
        now = dt_util.now()
        if (
            planned is not None
            and planned > now
            and (
                self.state.mode == MODE_FIXED_TIME
                or self.state.planned_price_cents is not None
            )
        ):
            self.state.status = STATUS_SCHEDULED
            self._schedule_timer(planned)
            self.notify_updated()
            if self.state.planned_price_cents is None:
                _LOGGER.info(
                    "Appliance %s restored fixed scheduled start at %s without "
                    "requiring electricity-price data",
                    self.name,
                    planned.isoformat(),
                )
            else:
                _LOGGER.info(
                    "Appliance %s restored scheduled start at %s for %.6f ct/kWh",
                    self.name,
                    planned.isoformat(),
                    self.state.planned_price_cents,
                )
            return
        try:
            await self.async_replan(announce_changes=False)
            if self.state.mode == MODE_NEXT_FAVORABLE and self.runtime.is_favorable_now():
                self.cancel_timer()
                self.hass.async_create_task(self.async_execute())
        except SchedulerError as err:
            self.cancel_timer()
            if self.state.mode == MODE_FIXED_TIME:
                self.state.armed = False
                self.state.status = STATUS_ERROR
            else:
                self.state.status = STATUS_WAITING_DATA
            self.state.last_error = str(err)
            self.notify_updated()

    async def async_handle_source_update(self) -> None:
        """Replan after ESC changes and immediately start in an active cheap phase."""
        if not self.state.armed or self.executing:
            return
        try:
            await self.async_replan(announce_changes=True)
            if not self.state.armed or self.executing:
                return
            if self.state.mode == MODE_NEXT_FAVORABLE and self.runtime.is_favorable_now():
                self.cancel_timer()
                await self.async_execute()
        except SchedulerError as err:
            if not self.state.armed:
                return
            self.state.last_error = str(err)
            if self._unsub_timer is None:
                self.state.status = STATUS_WAITING_DATA
            self.notify_updated()

    async def async_set_mode(self, mode: str) -> None:
        _LOGGER.info("Appliance %s start mode changed to %s", self.name, mode)
        self.state.mode = mode
        if not self.state.armed and not self.executing:
            self.state.status = STATUS_IDLE
            self.state.last_error = None
        self.notify_updated()
        if self.state.armed:
            await self._async_replan_after_user_change()

    async def async_set_scheduled_time(self, value: datetime) -> None:
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        localized = dt_util.as_local(value)
        _LOGGER.info(
            "Appliance %s fixed start time changed to %s",
            self.name,
            localized.isoformat(),
        )
        self.state.scheduled_time = localized.isoformat()
        if not self.state.armed and not self.executing:
            self.state.status = STATUS_IDLE
            self.state.last_error = None
        self.notify_updated()
        if self.state.armed and self.state.mode == MODE_FIXED_TIME:
            await self._async_replan_after_user_change()

    async def async_set_program(self, program: str) -> None:
        if program not in self.program_options:
            raise SchedulerError(f"Das Programm {program} ist nicht verfügbar.")
        _LOGGER.info("Appliance %s program changed to %s", self.name, program)
        self.state.selected_program = program
        if not self.state.armed and not self.executing:
            self.state.status = STATUS_IDLE
            self.state.last_error = None
        self.notify_updated()
        if self.state.armed:
            await self.runtime.async_announce(
                self._render_message(self.runtime.alexa_template("alexa_text_plan_changed")),
                quiet_hours_override=self.alexa_quiet_hours_override,
            )

    async def _async_replan_after_user_change(self) -> None:
        try:
            await self.async_replan(announce_changes=True)
        except SchedulerError as err:
            self.cancel_timer()
            self.state.armed = False
            self.state.status = STATUS_ERROR
            self.state.last_error = str(err)
            self.notify_updated()
            await self._announce_failure(str(err))
            raise

    async def async_set_armed(
        self, armed: bool, *, context: Context | None = None
    ) -> None:
        """Arm or cancel exactly one appliance start."""
        if armed:
            _LOGGER.info("Appliance %s start permission requested", self.name)
            if self.executing:
                raise SchedulerError(
                    "Für dieses Gerät wird bereits ein Start ausgeführt oder bestätigt."
                )
            if self.state.armed:
                return
            self.normalize_selected_program()
            self.state.armed = True
            try:
                await self.async_replan(announce_changes=False, context=context)
            except SchedulerError as err:
                self.state.armed = False
                self.state.status = STATUS_ERROR
                self.state.last_error = str(err)
                self.notify_updated()
                await self._announce_failure(str(err))
                raise

            immediate_start = (
                self.state.mode == MODE_NEXT_FAVORABLE
                and self.runtime.is_favorable_now()
            )
            if immediate_start:
                self.cancel_timer()
            await self.runtime.async_announce(
                self._render_message(self.runtime.alexa_template("alexa_text_activated")),
                quiet_hours_override=self.alexa_quiet_hours_override,
            )
            if immediate_start and self.state.armed:
                self.hass.async_create_task(self.async_execute(context=context))
            return

        if not self.state.armed:
            return
        _LOGGER.info("Appliance %s start permission cancellation requested", self.name)
        cancelled_schedule = self._schedule_phrase()
        self.cancel_timer()
        self.state.armed = False
        self.state.planned_start = None
        self.state.planned_price_cents = None
        self.state.status = STATUS_CANCELLED
        self.state.last_error = None
        self.notify_updated()
        await self.runtime.async_announce(
            self._render_message(
                self.runtime.alexa_template("alexa_text_deactivated"),
                schedule=cancelled_schedule,
            ),
            quiet_hours_override=self.alexa_quiet_hours_override,
        )

    async def async_replan(
        self,
        *,
        announce_changes: bool,
        context: Context | None = None,
    ) -> None:
        async with self._replan_lock:
            await self._async_replan_locked(
                announce_changes=announce_changes,
                context=context,
            )

    async def _async_replan_locked(
        self,
        *,
        announce_changes: bool,
        context: Context | None = None,
    ) -> None:
        previous_start = self.state.planned_start
        previous_price = self.state.planned_price_cents
        start = self._calculate_start()
        if start is None:
            raise MissingScheduleError(
                "Es konnte kein aktueller oder zukünftiger Startzeitpunkt ermittelt werden."
            )
        if start <= dt_util.now() - timedelta(seconds=5):
            raise MissingScheduleError("Der gewählte Startzeitpunkt liegt in der Vergangenheit.")

        price_eur = self.runtime.price_for(start)
        if price_eur is None and self.state.mode == MODE_NEXT_FAVORABLE:
            raise PriceUnavailableError(
                "Für den geplanten Günstigphasenstart liegt kein Strompreis im ESC-Sensor vor."
            )

        self.cancel_timer()
        self.state.planned_start = start.isoformat()
        self.state.planned_price_cents = (
            round(price_eur * 100, 6) if price_eur is not None else None
        )
        self.state.status = STATUS_SCHEDULED
        self.state.last_error = None
        self.notify_updated()
        if self.state.planned_price_cents is None:
            _LOGGER.info(
                "Appliance %s fixed start planned for %s without requiring "
                "electricity-price data",
                self.name,
                start.isoformat(),
            )
        else:
            _LOGGER.info(
                "Appliance %s start planned for %s at %.6f ct/kWh (mode=%s)",
                self.name,
                start.isoformat(),
                self.state.planned_price_cents,
                self.state.mode,
            )
        self._schedule_timer(start, context=context)

        changed = (
            previous_start != self.state.planned_start
            or previous_price != self.state.planned_price_cents
        )
        if announce_changes and changed:
            await self.runtime.async_announce(
                self._render_message(self.runtime.alexa_template("alexa_text_plan_changed")),
                quiet_hours_override=self.alexa_quiet_hours_override,
            )

    @callback
    def _schedule_timer(
        self, start: datetime, *, context: Context | None = None
    ) -> None:
        now = dt_util.now()
        if start <= now + timedelta(seconds=1):
            self.hass.async_create_task(self.async_execute(context=context))
            return
        self._unsub_timer = async_track_point_in_time(
            self.hass,
            lambda _: self.hass.async_create_task(self.async_execute(context=context)),
            start,
        )

    def _calculate_start(self) -> datetime | None:
        if self.state.mode == MODE_FIXED_TIME:
            return self.scheduled_time
        if self.state.mode == MODE_NEXT_FAVORABLE:
            return self.runtime.next_favorable_start()
        return None

    async def async_execute(self, *, context: Context | None = None) -> None:
        """Execute the configured one-shot start exactly once."""
        async with self._execution_lock:
            if not self.state.armed:
                return
            await self._async_execute_locked(context=context)

    async def _async_execute_locked(self, *, context: Context | None = None) -> None:
        self.cancel_timer()
        if self.state.mode == MODE_NEXT_FAVORABLE and not self.runtime.is_favorable_now():
            try:
                await self.async_replan(announce_changes=True, context=context)
            except SchedulerError as err:
                self.state.status = STATUS_WAITING_DATA
                self.state.last_error = str(err)
                self.notify_updated()
            return

        self._executing = True
        _LOGGER.info(
            "Appliance %s start sequence begins; program=%s, planned start=%s, "
            "planned price=%s ct/kWh",
            self.name,
            self.state.selected_program or "not selected",
            self.state.planned_start or "not planned",
            self.state.planned_price_cents
            if self.state.planned_price_cents is not None
            else "not planned",
        )
        self.state.status = STATUS_STARTING
        self.state.last_error = None
        self.notify_updated()
        planned_price = self.state.planned_price_cents
        try:
            if self._prepare_script is not None:
                await self._prepare_script.async_run(context=context)
            await self._async_apply_program(context=context)
            if self._start_script is not None:
                await self._start_script.async_run(context=context)
            elif not (
                self.program_entity
                and self.program_behavior == PROGRAM_BEHAVIOR_SELECT_STARTS_DEVICE
            ):
                raise SchedulerError("Für dieses Gerät wurde keine Startaktion konfiguriert.")
        except Exception as err:
            friendly_error = _friendly_start_error(err)
            _LOGGER.exception(
                "Starting appliance %s failed: %s",
                self.name,
                friendly_error,
            )
            self._finalize_failed_start(friendly_error)
            await self._announce_failure(friendly_error)
            return

        # The start command has been issued. Disarm immediately so no source update,
        # restart or timeout can trigger the appliance a second time.
        self.state.armed = False
        self.notify_updated()
        _LOGGER.info(
            "Appliance %s start command was issued; start permission was disabled",
            self.name,
        )

        if self.operating_state_entity:
            self.state.status = STATUS_WAITING_CONFIRMATION
            self.notify_updated()
            _LOGGER.info(
                "Appliance %s is waiting up to %d seconds for operating-state "
                "confirmation from %s",
                self.name,
                self.confirmation_timeout,
                self.operating_state_entity,
            )
            if not await self._async_wait_until_running():
                self.state.status = STATUS_START_UNCONFIRMED
                self.state.last_error = "Betriebszustand wurde nicht rechtzeitig bestätigt."
                self.state.planned_start = None
                self.state.planned_price_cents = None
                self._executing = False
                self.notify_updated()
                await self.runtime.async_announce(
                    self._render_message(
                        self.runtime.alexa_template("alexa_text_confirmation_failed"),
                        error=self.state.last_error,
                    ),
                    level=logging.WARNING,
                    quiet_hours_override=self.alexa_quiet_hours_override,
                )
                return

        started = dt_util.now()
        actual_price_eur = self.runtime.current_price()
        actual_price_cents = (
            round(actual_price_eur * 100, 6)
            if actual_price_eur is not None
            else planned_price
        )
        if self.operating_state_entity:
            _LOGGER.info(
                "Appliance %s operating state was confirmed by %s",
                self.name,
                self.operating_state_entity,
            )
        self.state.status = STATUS_STARTED
        self.state.last_started = started.isoformat()
        self.state.last_started_price_cents = actual_price_cents
        self.state.last_error = None
        self.state.planned_start = None
        self.state.planned_price_cents = None
        self._executing = False
        self.notify_updated()
        await self.runtime.async_announce(
            self._render_message(
                self.runtime.alexa_template("alexa_text_started"),
                started=started,
                price_cents=actual_price_cents,
            ),
            quiet_hours_override=self.alexa_quiet_hours_override,
        )

    async def _async_apply_program(self, *, context: Context | None = None) -> None:
        if not self.program_entity:
            return
        self.normalize_selected_program()
        program = self.state.selected_program
        if not program:
            raise SchedulerError("Es wurde kein Programm ausgewählt.")
        options = self.program_options
        if options and program not in options:
            raise SchedulerError(f"Das ausgewählte Programm {program} ist nicht verfügbar.")
        domain = self.program_entity.split(".", 1)[0]
        _LOGGER.info(
            "Appliance %s applies program %s to %s",
            self.name,
            program,
            self.program_entity,
        )
        await self.hass.services.async_call(
            domain,
            "select_option",
            {"entity_id": self.program_entity, "option": program},
            blocking=True,
            context=context,
        )

    def is_running(self) -> bool:
        if not self.operating_state_entity:
            return False
        state = self.hass.states.get(self.operating_state_entity)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False
        return state.state.casefold() in self.running_states

    async def _async_wait_until_running(self) -> bool:
        if self.is_running():
            return True
        entity_id = self.operating_state_entity
        if not entity_id:
            return True
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

        @callback
        def state_changed(_event: Event) -> None:
            if self.is_running() and not future.done():
                future.set_result(True)

        unsub = async_track_state_change_event(self.hass, [entity_id], state_changed)
        try:
            async with asyncio.timeout(self.confirmation_timeout):
                return await future
        except TimeoutError:
            return False
        finally:
            unsub()

    def _finalize_failed_start(self, error: str) -> None:
        self.state.armed = False
        self.state.status = STATUS_ERROR
        self.state.last_error = error
        self.state.planned_start = None
        self.state.planned_price_cents = None
        self._executing = False
        self.notify_updated()

    async def _announce_failure(self, error: str) -> None:
        await self.runtime.async_announce(
            self._render_message(
                self.runtime.alexa_template("alexa_text_start_failed"),
                error=error,
            ),
            level=logging.ERROR,
            quiet_hours_override=self.alexa_quiet_hours_override,
        )

    def _render_message(
        self,
        template: str,
        *,
        schedule: str | None = None,
        started: datetime | None = None,
        price_cents: float | None = None,
        error: str = "",
    ) -> str:
        start = started or self.planned_start or dt_util.now()
        values = {
            "device": self.name,
            "program": self.state.selected_program or "",
            "program_phrase": self._program_phrase(),
            "start_date": self._format_date(start),
            "start_time": self._format_time(start),
            "price": self._price_phrase(
                price_cents
                if price_cents is not None
                else self.state.planned_price_cents
            ),
            "schedule": schedule or self._schedule_phrase(),
            "error": error,
        }
        return render_message_template(template, values)

    def _schedule_phrase(self) -> str:
        start = self.planned_start
        if start is None:
            return (
                "Es ist noch kein Startzeitpunkt geplant"
                if self.runtime.is_german
                else "No start time has been scheduled yet"
            )
        now = dt_util.now()
        if self.runtime.is_german:
            if abs((start - now).total_seconds()) <= 60:
                when = "Das Gerät startet jetzt"
            elif start.date() == now.date():
                when = f"Das Gerät startet heute um {self._format_time(start)} Uhr"
            elif start.date() == (now + timedelta(days=1)).date():
                when = f"Das Gerät startet morgen um {self._format_time(start)} Uhr"
            else:
                when = f"Das Gerät startet am {self._format_date(start)} um {self._format_time(start)} Uhr"
            if self.state.planned_price_cents is None:
                return when
            return f"{when} zum Strompreis von {self._price_phrase(self.state.planned_price_cents)}"

        if abs((start - now).total_seconds()) <= 60:
            when = "The appliance starts now"
        elif start.date() == now.date():
            when = f"The appliance starts today at {self._format_time(start)}"
        elif start.date() == (now + timedelta(days=1)).date():
            when = f"The appliance starts tomorrow at {self._format_time(start)}"
        else:
            when = f"The appliance starts on {self._format_date(start)} at {self._format_time(start)}"
        if self.state.planned_price_cents is None:
            return when
        return f"{when} at an electricity price of {self._price_phrase(self.state.planned_price_cents)}"

    def _program_phrase(self) -> str:
        if not self.state.selected_program:
            return ""
        if self.runtime.is_german:
            return f"mit dem Programm {self.state.selected_program}"
        return f"using the {self.state.selected_program} program"

    def _format_date(self, value: datetime) -> str:
        return value.strftime("%d.%m.%Y" if self.runtime.is_german else "%Y-%m-%d")

    @staticmethod
    def _format_time(value: datetime) -> str:
        return value.strftime("%H:%M")

    def _price_phrase(self, value: float | None) -> str:
        if value is None:
            # An armed plan is rejected before this can occur; this fallback only
            # protects manually damaged storage data.
            return "kein gültiger Preis" if self.runtime.is_german else "no valid price"
        formatted = f"{value:.2f}"
        if self.runtime.is_german:
            formatted = formatted.replace(".", ",")
            return f"{formatted} Cent pro Kilowattstunde"
        return f"{formatted} cents per kilowatt-hour"

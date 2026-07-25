"""Config flow for Energy Appliance Scheduler."""

from __future__ import annotations

from datetime import time as dt_time
from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    FlowType,
    OptionsFlow,
    SubentryFlowContext,
    SubentryFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.helpers.script import async_validate_actions_config

from .const import (
    ALEXA_DOMAIN,
    ALEXA_MESSAGE_TYPES,
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
    CONF_NAME,
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
    DEFAULT_PROGRAM_BEHAVIOR,
    DEFAULT_RUNNING_STATES,
    DEFAULT_START_CONFIRMATION_TIMEOUT,
    DOMAIN,
    ESC_DOMAIN,
    MAX_ALEXA_VOLUME_PERCENT,
    MAX_START_CONFIRMATION_TIMEOUT,
    MIN_ALEXA_VOLUME_PERCENT,
    MIN_START_CONFIRMATION_TIMEOUT,
    PROGRAM_BEHAVIOR_SELECT_STARTS_DEVICE,
    PROGRAM_BEHAVIORS,
    SUBENTRY_TYPE_APPLIANCE,
)
from .messages import validate_message_template


def _entity_selector(
    *, integration: str | None = None, domain: str | list[str] | None = None, multiple: bool = False
):
    config: dict[str, Any] = {"multiple": multiple}
    if integration is not None:
        config["integration"] = integration
    if domain is not None:
        config["domain"] = domain
    return selector.EntitySelector(selector.EntitySelectorConfig(**config))


def _marker(key: str, defaults: dict[str, Any], *, required: bool = True):
    """Build a schema marker with a suggested value but no invalid None default."""
    marker = vol.Required if required else vol.Optional
    if key in defaults and defaults[key] is not None:
        return marker(key, description={"suggested_value": defaults[key]})
    return marker(key)


def _default_alexa_texts(hass: HomeAssistant) -> dict[str, str]:
    """Return localized editable defaults."""
    language = str(getattr(hass.config, "language", "en") or "en").lower()
    return dict(DEFAULT_ALEXA_TEXTS_DE if language.startswith("de") else DEFAULT_ALEXA_TEXTS_EN)


def _normalize_time_value(value: Any, default: str) -> str:
    """Return a stable HH:MM:SS value accepted by the runtime."""
    if isinstance(value, dt_time):
        return value.replace(microsecond=0).isoformat()
    raw = str(value or default).strip()
    try:
        return dt_time.fromisoformat(raw).replace(microsecond=0).isoformat()
    except ValueError:
        return default


def _normalize_main_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize global settings before storing them in the config entry."""
    data = dict(user_input)
    data[CONF_ALEXA_QUIET_HOURS_ENABLED] = bool(
        data.get(
            CONF_ALEXA_QUIET_HOURS_ENABLED,
            DEFAULT_ALEXA_QUIET_HOURS_ENABLED,
        )
    )
    data[CONF_ALEXA_QUIET_HOURS_START] = _normalize_time_value(
        data.get(CONF_ALEXA_QUIET_HOURS_START),
        DEFAULT_ALEXA_QUIET_HOURS_START,
    )
    data[CONF_ALEXA_QUIET_HOURS_END] = _normalize_time_value(
        data.get(CONF_ALEXA_QUIET_HOURS_END),
        DEFAULT_ALEXA_QUIET_HOURS_END,
    )
    try:
        volume = int(round(float(data.get(CONF_ALEXA_VOLUME_PERCENT))))
    except (TypeError, ValueError):
        volume = DEFAULT_ALEXA_VOLUME_PERCENT
    data[CONF_ALEXA_VOLUME_PERCENT] = max(
        MIN_ALEXA_VOLUME_PERCENT,
        min(MAX_ALEXA_VOLUME_PERCENT, volume),
    )
    return data


def _main_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = dict(defaults or {})
    defaults.setdefault(CONF_ALEXA_MESSAGE_TYPE, DEFAULT_ALEXA_MESSAGE_TYPE)
    defaults.setdefault(
        CONF_ALEXA_QUIET_HOURS_ENABLED, DEFAULT_ALEXA_QUIET_HOURS_ENABLED
    )
    defaults.setdefault(CONF_ALEXA_QUIET_HOURS_START, DEFAULT_ALEXA_QUIET_HOURS_START)
    defaults.setdefault(CONF_ALEXA_QUIET_HOURS_END, DEFAULT_ALEXA_QUIET_HOURS_END)
    defaults.setdefault(CONF_ALEXA_VOLUME_PERCENT, DEFAULT_ALEXA_VOLUME_PERCENT)
    return vol.Schema(
        {
            _marker(CONF_FAVORABLE_PHASE_SENSOR, defaults): _entity_selector(
                integration=ESC_DOMAIN, domain="sensor"
            ),
            _marker(CONF_FAVORABLE_NOW_SENSOR, defaults): _entity_selector(
                integration=ESC_DOMAIN, domain="binary_sensor"
            ),
            _marker(CONF_PRICE_SENSOR, defaults): _entity_selector(
                integration=ESC_DOMAIN, domain="sensor"
            ),
            _marker(CONF_ALEXA_MEDIA_PLAYERS, defaults): _entity_selector(
                integration=ALEXA_DOMAIN, domain="media_player", multiple=True
            ),
            _marker(CONF_ALEXA_MESSAGE_TYPE, defaults): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ALEXA_MESSAGE_TYPES),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="alexa_message_type",
                )
            ),
            _marker(CONF_ALEXA_QUIET_HOURS_ENABLED, defaults): (
                selector.BooleanSelector()
            ),
            _marker(CONF_ALEXA_QUIET_HOURS_START, defaults): selector.TimeSelector(),
            _marker(CONF_ALEXA_QUIET_HOURS_END, defaults): selector.TimeSelector(),
            _marker(CONF_ALEXA_VOLUME_PERCENT, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_ALEXA_VOLUME_PERCENT,
                    max=MAX_ALEXA_VOLUME_PERCENT,
                    step=1,
                    mode=selector.NumberSelectorMode.SLIDER,
                    unit_of_measurement="%",
                )
            ),
        }
    )


def _alexa_text_schema(defaults: dict[str, Any]) -> vol.Schema:
    multiline = selector.TextSelector(
        selector.TextSelectorConfig(multiline=True)
    )
    return vol.Schema({_marker(key, defaults): multiline for key in ALEXA_TEXT_KEYS})


def _program_behavior_selector():
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(PROGRAM_BEHAVIORS),
            mode=selector.SelectSelectorMode.DROPDOWN,
            translation_key="program_behavior",
        )
    )


def _appliance_details_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = dict(defaults or {})
    defaults.setdefault(CONF_PROGRAM_BEHAVIOR, DEFAULT_PROGRAM_BEHAVIOR)
    return vol.Schema(
        {
            _marker(CONF_NAME, defaults): selector.TextSelector(),
            _marker(CONF_ICON, defaults, required=False): selector.IconSelector(),
            _marker(CONF_PROGRAM_ENTITY, defaults, required=False): _entity_selector(
                domain=["select", "input_select"]
            ),
            _marker(CONF_PROGRAM_BEHAVIOR, defaults): _program_behavior_selector(),
        }
    )


def _appliance_control_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = dict(defaults or {})
    defaults.setdefault(CONF_RUNNING_STATES, DEFAULT_RUNNING_STATES)
    defaults.setdefault(
        CONF_START_CONFIRMATION_TIMEOUT, DEFAULT_START_CONFIRMATION_TIMEOUT
    )
    return vol.Schema(
        {
            _marker(CONF_PREPARE_ACTIONS, defaults, required=False): selector.ActionSelector(),
            _marker(CONF_START_ACTIONS, defaults, required=False): selector.ActionSelector(),
            _marker(CONF_OPERATING_STATE_ENTITY, defaults, required=False): _entity_selector(),
            _marker(CONF_RUNNING_STATES, defaults, required=False): selector.TextSelector(),
            _marker(CONF_START_CONFIRMATION_TIMEOUT, defaults): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_START_CONFIRMATION_TIMEOUT,
                    max=MAX_START_CONFIRMATION_TIMEOUT,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )
            ),
        }
    )


def _validate_main_input(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input.get(CONF_ALEXA_MEDIA_PLAYERS):
        errors[CONF_ALEXA_MEDIA_PLAYERS] = "at_least_one_alexa"
    if (
        user_input.get(
            CONF_ALEXA_QUIET_HOURS_ENABLED,
            DEFAULT_ALEXA_QUIET_HOURS_ENABLED,
        )
        and user_input.get(CONF_ALEXA_QUIET_HOURS_START)
        == user_input.get(CONF_ALEXA_QUIET_HOURS_END)
    ):
        errors[CONF_ALEXA_QUIET_HOURS_END] = "quiet_hours_identical"
    return errors


def _validate_alexa_texts(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    for key in ALEXA_TEXT_KEYS:
        value = str(user_input.get(key, "")).strip()
        if not value:
            errors[key] = "message_required"
        elif not validate_message_template(value):
            errors[key] = "invalid_message_template"
    return errors


async def _async_validate_appliance_input(
    hass: HomeAssistant,
    entry: ConfigEntry,
    user_input: dict[str, Any],
    *,
    exclude_subentry_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Normalize one appliance and return field errors."""
    data = dict(user_input)
    errors: dict[str, str] = {}
    name = str(data.get(CONF_NAME, "")).strip()
    data[CONF_NAME] = name
    if not name:
        errors[CONF_NAME] = "name_required"
    elif any(
        subentry.subentry_id != exclude_subentry_id
        and subentry.title.casefold() == name.casefold()
        for subentry in entry.subentries.values()
    ):
        errors[CONF_NAME] = "duplicate_name"

    program_entity = data.get(CONF_PROGRAM_ENTITY)
    behavior = data.get(CONF_PROGRAM_BEHAVIOR, DEFAULT_PROGRAM_BEHAVIOR)
    start_actions = data.get(CONF_START_ACTIONS)
    if not start_actions and not (
        program_entity and behavior == PROGRAM_BEHAVIOR_SELECT_STARTS_DEVICE
    ):
        errors[CONF_START_ACTIONS] = "start_actions_required"

    for action_key in (CONF_PREPARE_ACTIONS, CONF_START_ACTIONS):
        actions = data.get(action_key)
        if not actions:
            data.pop(action_key, None)
            continue
        try:
            data[action_key] = await async_validate_actions_config(hass, actions)
        except vol.Invalid:
            errors[action_key] = "invalid_actions"

    running_states = str(data.get(CONF_RUNNING_STATES, "") or "").strip()
    operating_entity = data.get(CONF_OPERATING_STATE_ENTITY)
    if operating_entity and not running_states:
        errors[CONF_RUNNING_STATES] = "running_states_required"
    data[CONF_RUNNING_STATES] = running_states
    data[CONF_START_CONFIRMATION_TIMEOUT] = int(
        data.get(CONF_START_CONFIRMATION_TIMEOUT, DEFAULT_START_CONFIRMATION_TIMEOUT)
    )
    return data, errors


class EnergyApplianceSchedulerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the single main configuration entry."""

    VERSION = 2

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> "SchedulerOptionsFlow":
        """Return the post-setup configuration flow."""
        return SchedulerOptionsFlow()

    async def async_on_create_entry(self, result: ConfigFlowResult) -> ConfigFlowResult:
        """Open the first appliance flow immediately after base setup."""
        subentry_result = await self.hass.config_entries.subentries.async_init(
            (result["result"].entry_id, SUBENTRY_TYPE_APPLIANCE),
            context=SubentryFlowContext(source=SOURCE_USER),
        )
        result["next_flow"] = (
            FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_APPLIANCE: ApplianceSubentryFlow}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the actual settings directly, without a confirmation step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if not self.hass.config_entries.async_entries(ESC_DOMAIN):
            return self.async_abort(reason="energy_storage_control_required")
        if not self.hass.config_entries.async_entries(ALEXA_DOMAIN):
            return self.async_abort(reason="alexa_media_required")

        errors: dict[str, str] = {}
        normalized_input: dict[str, Any] | None = None
        if user_input is not None:
            normalized_input = _normalize_main_input(user_input)
            errors = _validate_main_input(normalized_input)
            if not errors:
                self._data.update(normalized_input)
                return await self.async_step_alexa_texts()
        return self.async_show_form(
            step_id="user",
            data_schema=_main_schema(normalized_input),
            errors=errors,
        )

    async def async_step_alexa_texts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure editable Alexa texts."""
        defaults = _default_alexa_texts(self.hass) | (user_input or {})
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_alexa_texts(user_input)
            if not errors:
                self._data.update({key: str(user_input[key]).strip() for key in ALEXA_TEXT_KEYS})
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Energy Appliance Scheduler", data=self._data)
        return self.async_show_form(
            step_id="alexa_texts",
            data_schema=_alexa_text_schema(defaults),
            errors=errors,
        )


class SchedulerOptionsFlow(OptionsFlow):
    """Edit global sensors, Alexa targets and Alexa messages after setup."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        defaults = dict(self.config_entry.data) | dict(self.config_entry.options)
        errors: dict[str, str] = {}
        normalized_input: dict[str, Any] | None = None
        if user_input is not None:
            normalized_input = _normalize_main_input(user_input)
            errors = _validate_main_input(normalized_input)
            if not errors:
                self._data.update(normalized_input)
                return await self.async_step_alexa_texts()
        return self.async_show_form(
            step_id="init",
            data_schema=_main_schema(defaults | (normalized_input or {})),
            errors=errors,
        )

    async def async_step_alexa_texts(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        defaults = (
            _default_alexa_texts(self.hass)
            | dict(self.config_entry.data)
            | dict(self.config_entry.options)
            | (user_input or {})
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_alexa_texts(user_input)
            if not errors:
                self._data.update({key: str(user_input[key]).strip() for key in ALEXA_TEXT_KEYS})
                return self.async_create_entry(title="", data=self._data)
        return self.async_show_form(
            step_id="alexa_texts",
            data_schema=_alexa_text_schema(defaults),
            errors=errors,
        )


class ApplianceSubentryFlow(ConfigSubentryFlow):
    """Add and reconfigure appliance subentries."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a new appliance: details and optional program source."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input.get(CONF_NAME, "")).strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif any(
                subentry.title.casefold() == name.casefold()
                for subentry in self._get_entry().subentries.values()
            ):
                errors[CONF_NAME] = "duplicate_name"
            else:
                self._data.update(user_input | {CONF_NAME: name})
                return await self.async_step_controls()
        return self.async_show_form(
            step_id="user",
            data_schema=_appliance_details_schema(user_input),
            errors=errors,
        )

    async def async_step_controls(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure actions and optional operating-state confirmation."""
        errors: dict[str, str] = {}
        if user_input is not None:
            combined = self._data | user_input
            data, errors = await _async_validate_appliance_input(
                self.hass, self._get_entry(), combined
            )
            if not errors:
                title = data.pop(CONF_NAME)
                return self.async_create_entry(title=title, data=data)
        return self.async_show_form(
            step_id="controls",
            data_schema=_appliance_control_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit appliance details and optional program source."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        defaults = {CONF_NAME: subentry.title} | dict(subentry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input.get(CONF_NAME, "")).strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif any(
                candidate.subentry_id != subentry.subentry_id
                and candidate.title.casefold() == name.casefold()
                for candidate in entry.subentries.values()
            ):
                errors[CONF_NAME] = "duplicate_name"
            else:
                self._data.update(user_input | {CONF_NAME: name})
                return await self.async_step_reconfigure_controls()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_appliance_details_schema(defaults | (user_input or {})),
            errors=errors,
        )

    async def async_step_reconfigure_controls(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit appliance actions and operating-state confirmation."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        defaults = dict(subentry.data)
        errors: dict[str, str] = {}
        if user_input is not None:
            combined = self._data | user_input
            data, errors = await _async_validate_appliance_input(
                self.hass,
                entry,
                combined,
                exclude_subentry_id=subentry.subentry_id,
            )
            if not errors:
                title = data.pop(CONF_NAME)
                return self.async_update_and_abort(
                    entry,
                    subentry,
                    title=title,
                    data=data,
                )
        return self.async_show_form(
            step_id="reconfigure_controls",
            data_schema=_appliance_control_schema(defaults | (user_input or {})),
            errors=errors,
        )

"""Constants for Energy Appliance Scheduler."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "energy_appliance_scheduler"
NAME = "Energy Appliance Scheduler"
MANUFACTURER = "Q14siX"
MODEL = "Energy-controlled appliance"
ESC_DOMAIN = "energy_storage_control"
ALEXA_DOMAIN = "alexa_media"

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.DATETIME,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
)

SUBENTRY_TYPE_APPLIANCE = "appliance"

CONF_FAVORABLE_PHASE_SENSOR = "favorable_phase_sensor"
CONF_FAVORABLE_NOW_SENSOR = "favorable_now_sensor"
CONF_PRICE_SENSOR = "price_sensor"
CONF_ALEXA_MEDIA_PLAYERS = "alexa_media_players"
CONF_ALEXA_MESSAGE_TYPE = "alexa_message_type"
CONF_ALEXA_QUIET_HOURS_ENABLED = "alexa_quiet_hours_enabled"
CONF_ALEXA_QUIET_HOURS_START = "alexa_quiet_hours_start"
CONF_ALEXA_QUIET_HOURS_END = "alexa_quiet_hours_end"
CONF_ALEXA_VOLUME_PERCENT = "alexa_volume_percent"

CONF_ALEXA_TEXT_ACTIVATED = "alexa_text_activated"
CONF_ALEXA_TEXT_DEACTIVATED = "alexa_text_deactivated"
CONF_ALEXA_TEXT_PLAN_CHANGED = "alexa_text_plan_changed"
CONF_ALEXA_TEXT_STARTED = "alexa_text_started"
CONF_ALEXA_TEXT_START_FAILED = "alexa_text_start_failed"
CONF_ALEXA_TEXT_CONFIRMATION_FAILED = "alexa_text_confirmation_failed"
ALEXA_TEXT_KEYS = (
    CONF_ALEXA_TEXT_ACTIVATED,
    CONF_ALEXA_TEXT_DEACTIVATED,
    CONF_ALEXA_TEXT_PLAN_CHANGED,
    CONF_ALEXA_TEXT_STARTED,
    CONF_ALEXA_TEXT_START_FAILED,
    CONF_ALEXA_TEXT_CONFIRMATION_FAILED,
)
ALEXA_TEMPLATE_FIELDS = frozenset(
    {
        "device",
        "program",
        "program_phrase",
        "start_date",
        "start_time",
        "price",
        "schedule",
        "error",
    }
)

CONF_NAME = "name"
CONF_ICON = "icon"
CONF_PROGRAM_ENTITY = "program_entity"
CONF_PROGRAM_BEHAVIOR = "program_behavior"
CONF_PREPARE_ACTIONS = "prepare_actions"
CONF_START_ACTIONS = "start_actions"
CONF_OPERATING_STATE_ENTITY = "operating_state_entity"
CONF_RUNNING_STATES = "running_states"
CONF_START_CONFIRMATION_TIMEOUT = "start_confirmation_timeout"

PROGRAM_BEHAVIOR_SELECT_THEN_START = "select_then_start"
PROGRAM_BEHAVIOR_SELECT_STARTS_DEVICE = "select_starts_device"
PROGRAM_BEHAVIORS = (
    PROGRAM_BEHAVIOR_SELECT_THEN_START,
    PROGRAM_BEHAVIOR_SELECT_STARTS_DEVICE,
)

ALEXA_MESSAGE_TTS = "tts"
ALEXA_MESSAGE_ANNOUNCE = "announce"
ALEXA_MESSAGE_TYPES = (ALEXA_MESSAGE_TTS, ALEXA_MESSAGE_ANNOUNCE)

MODE_NEXT_FAVORABLE = "next_favorable"
MODE_FIXED_TIME = "fixed_time"
START_MODES = (MODE_NEXT_FAVORABLE, MODE_FIXED_TIME)

STATUS_IDLE = "idle"
STATUS_SCHEDULED = "scheduled"
STATUS_STARTING = "starting"
STATUS_WAITING_CONFIRMATION = "waiting_confirmation"
STATUS_STARTED = "started"
STATUS_START_UNCONFIRMED = "start_unconfirmed"
STATUS_CANCELLED = "cancelled"
STATUS_WAITING_DATA = "waiting_data"
STATUS_ERROR = "error"
STATUS_OPTIONS = (
    STATUS_IDLE,
    STATUS_SCHEDULED,
    STATUS_STARTING,
    STATUS_WAITING_CONFIRMATION,
    STATUS_STARTED,
    STATUS_START_UNCONFIRMED,
    STATUS_CANCELLED,
    STATUS_WAITING_DATA,
    STATUS_ERROR,
)

STORAGE_VERSION = 1
STORAGE_KEY = DOMAIN
SAVE_DELAY_SECONDS = 1

DEFAULT_ICON = "mdi:home-lightning-bolt"
DEFAULT_ALEXA_MESSAGE_TYPE = ALEXA_MESSAGE_TTS
DEFAULT_ALEXA_QUIET_HOURS_ENABLED = True
DEFAULT_ALEXA_QUIET_HOURS_START = "22:00:00"
DEFAULT_ALEXA_QUIET_HOURS_END = "06:00:00"
DEFAULT_ALEXA_VOLUME_PERCENT = 40
MIN_ALEXA_VOLUME_PERCENT = 1
MAX_ALEXA_VOLUME_PERCENT = 100
DEFAULT_MODE = MODE_NEXT_FAVORABLE
DEFAULT_PROGRAM_BEHAVIOR = PROGRAM_BEHAVIOR_SELECT_THEN_START
DEFAULT_RUNNING_STATES = "on,running,active,run,working"
DEFAULT_START_CONFIRMATION_TIMEOUT = 120
MIN_START_CONFIRMATION_TIMEOUT = 5
MAX_START_CONFIRMATION_TIMEOUT = 900

DEFAULT_ALEXA_TEXTS_DE = {
    CONF_ALEXA_TEXT_ACTIVATED: (
        "Der Start von {device} wurde aktiviert. {schedule}. {program_phrase}"
    ),
    CONF_ALEXA_TEXT_DEACTIVATED: (
        "Der geplante Start von {device} wurde deaktiviert. Zuvor war geplant: "
        "{schedule}. Das Gerät wird nicht automatisch gestartet."
    ),
    CONF_ALEXA_TEXT_PLAN_CHANGED: (
        "Der Startplan für {device} wurde aktualisiert. {schedule}. {program_phrase}"
    ),
    CONF_ALEXA_TEXT_STARTED: (
        "{device} wurde um {start_time} Uhr {program_phrase} zum Strompreis von "
        "{price} gestartet."
    ),
    CONF_ALEXA_TEXT_START_FAILED: (
        "{device} konnte nicht gestartet werden. {error}"
    ),
    CONF_ALEXA_TEXT_CONFIRMATION_FAILED: (
        "Der Startbefehl für {device} wurde ausgeführt, aber der Betriebszustand "
        "konnte nicht bestätigt werden. Bitte prüfe das Gerät."
    ),
}

DEFAULT_ALEXA_TEXTS_EN = {
    CONF_ALEXA_TEXT_ACTIVATED: (
        "The start of {device} has been enabled. {schedule}. {program_phrase}"
    ),
    CONF_ALEXA_TEXT_DEACTIVATED: (
        "The scheduled start of {device} has been disabled. The previous plan was: "
        "{schedule}. The appliance will not start automatically."
    ),
    CONF_ALEXA_TEXT_PLAN_CHANGED: (
        "The start plan for {device} has been updated. {schedule}. {program_phrase}"
    ),
    CONF_ALEXA_TEXT_STARTED: (
        "{device} started at {start_time} {program_phrase} at an electricity price "
        "of {price}."
    ),
    CONF_ALEXA_TEXT_START_FAILED: (
        "{device} could not be started. {error}"
    ),
    CONF_ALEXA_TEXT_CONFIRMATION_FAILED: (
        "The start command for {device} was sent, but the operating state could not "
        "be confirmed. Please check the appliance."
    ),
}

PRICE_TIME_KEYS = (
    "start_time",
    "starts_at",
    "startsAt",
    "start",
    "time",
    "timestamp",
)
PRICE_VALUE_KEYS = (
    "price_per_kwh",
    "total",
    "price",
    "energy_price",
    "value",
)

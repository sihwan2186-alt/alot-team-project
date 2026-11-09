from dataclasses import dataclass, field


@dataclass
class Room:
    room_id: str
    building_code: str
    building_name: str
    room_number: str
    floor: str
    floor_verified: bool = False


@dataclass
class RoomProfile:
    room_id: str
    capacity: int
    area_m2: float
    volume_m3: float


@dataclass
class SimulationConfig:
    start_date: str = "2026-09-01"
    days: int = 30
    step_minutes: int = 1
    seed: int = 20261102


@dataclass
class Reservation:
    reservation_id: str
    room_id: str
    created_at: str
    start_time: str
    end_time: str
    reserved_count: int
    status: str
    is_no_show: bool


@dataclass
class OccupancyState:
    count: int = 0


@dataclass
class EnvironmentState:
    temperature_c: float = 24.0
    humidity_pct: float = 55.0
    co2_ppm: float = 425.0
    illuminance_lux: float = 0.0
    noise_dba: float = 30.0
    absolute_humidity_g_m3: float = 12.0


@dataclass
class FacilityState:
    hvac_mode: str = "off"
    hvac_on: bool = False
    ventilation_on: bool = False
    ventilation_level: float = 0.0
    lighting_on: bool = False
    lighting_level: float = 0.0
    equipment_fault_active: bool = False
    last_changes: dict = field(default_factory=dict)


@dataclass
class SensorReading:
    timestamp: str
    room_id: str
    temperature_c: float | None
    humidity_pct: float | None
    co2_ppm: float | None
    illuminance_lux: float | None
    noise_dba: float | None
    occupancy_count: int | None


@dataclass
class SensorFault:
    kind: str
    variable: str
    start: int
    end: int
    stuck_value: float | None = None


@dataclass
class ControlAction:
    action_id: str
    timestamp: str
    room_id: str
    controller_type: str
    target_device: str
    previous_state: str
    requested_state: str
    action_reason: str
    applied_successfully: bool


@dataclass
class EnergyReading:
    hvac_power_kw: float
    ventilation_power_kw: float
    lighting_power_kw: float
    standby_power_kw: float
    total_power_kw: float
    interval_energy_kwh: float


@dataclass
class SimulationEvent:
    event_id: str
    timestamp: str
    room_id: str
    event_type: str
    count_delta: int
    resulting_occupancy: int
    reservation_id: str = ""

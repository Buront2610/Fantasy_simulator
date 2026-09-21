"""Persisted physical whereabouts, distinct from a character's residence."""

from dataclasses import asdict, dataclass, field
from math import isfinite


@dataclass(frozen=True)
class TravelLeg:
    origin: str
    destination: str
    cost: float
    route_id: str | None = None

    def __post_init__(self) -> None:
        if (not isinstance(self.origin, str) or not isinstance(self.destination, str)
                or not self.origin or not self.destination or self.origin == self.destination):
            raise ValueError("Travel leg requires distinct locations")
        if type(self.cost) not in (int, float) or not isfinite(self.cost) or self.cost <= 0:
            raise ValueError("Travel cost must be a positive finite number")
        if self.route_id is not None and (not isinstance(self.route_id, str) or not self.route_id):
            raise ValueError("Invalid travel route ID")


@dataclass
class AdventureItinerary:
    current_site_id: str
    remaining_legs: list[TravelLeg] = field(default_factory=list)
    active_leg: TravelLeg | None = None
    departure_tick: int | None = None
    arrival_tick: int | None = None
    waiting_for_route: bool = False
    visited_destination: bool = False

    @property
    def presence_location_id(self) -> str | None:
        return None if self.active_leg is not None else self.current_site_id

    def validate(self) -> None:
        if not isinstance(self.current_site_id, str) or not self.current_site_id:
            raise ValueError("Itinerary requires a current site")
        if type(self.waiting_for_route) is not bool or type(self.visited_destination) is not bool:
            raise ValueError("Invalid route waiting flag")
        if self.active_leg is None:
            if self.departure_tick is not None or self.arrival_tick is not None:
                raise ValueError("Stationary itinerary cannot have travel ticks")
        else:
            if self.active_leg.origin != self.current_site_id or self.waiting_for_route:
                raise ValueError("Active leg conflicts with itinerary position")
            if (type(self.departure_tick) is not int or type(self.arrival_tick) is not int
                    or self.departure_tick < 0 or self.arrival_tick <= self.departure_tick):
                raise ValueError("Invalid travel interval")
        previous = self.active_leg.destination if self.active_leg else self.current_site_id
        for leg in self.remaining_legs:
            if leg.origin != previous:
                raise ValueError("Disconnected itinerary")
            previous = leg.destination

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AdventureItinerary":
        result = cls(
            current_site_id=data["current_site_id"],
            remaining_legs=[TravelLeg(**leg) for leg in data.get("remaining_legs", [])],
            active_leg=TravelLeg(**data["active_leg"]) if data.get("active_leg") else None,
            departure_tick=data.get("departure_tick"), arrival_tick=data.get("arrival_tick"),
            waiting_for_route=data.get("waiting_for_route", False),
            visited_destination=data.get("visited_destination", False),
        )
        result.validate()
        return result


def affected_location_ids(run, world=None) -> list[str]:
    locations = [run.origin, run.destination]
    if run.itinerary is not None:
        locations.append(run.itinerary.current_site_id)
        if run.itinerary.active_leg is not None:
            locations.append(run.itinerary.active_leg.destination)
    if world is not None and run.objective is not None and run.objective.target_id:
        target = world.get_character_by_id(run.objective.target_id)
        if target is not None and target.location_id:
            locations.append(target.location_id)
    return list(dict.fromkeys(locations))

"""Values stored by the world's asset ledger, separate from display strings."""

from dataclasses import asdict, dataclass, field
from typing import Any


RESOURCES = frozenset({"moon_silver", "monster_trophy"})
ARTIFACT_KINDS = frozenset({"ancient_relic", "lore_fragment"})


def identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Invalid {label}")
    return value


@dataclass(frozen=True, order=True)
class AssetRef:
    kind: str
    reference_id: str

    def __post_init__(self) -> None:
        if self.kind not in ("character", "site"):
            raise ValueError("Unknown asset reference kind")
        identifier(self.reference_id, "asset reference")

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "id": self.reference_id}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetRef":
        return cls(data["kind"], data["id"])


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    kind: str
    origin_site_id: str
    custodian: AssetRef
    owner: AssetRef | None = None
    charges: int = 0
    maker_id: str | None = None
    creation_year: int | None = None
    material: str = ""
    purpose: str = ""
    inscription: str = ""
    inscription_language: str | None = None
    inscription_stage: str | None = None
    history: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.custodian, AssetRef) or (
            self.owner is not None and not isinstance(self.owner, AssetRef)
        ):
            raise ValueError("Invalid artifact custody or ownership")
        identifier(self.artifact_id, "artifact ID")
        identifier(self.origin_site_id, "artifact origin")
        if self.kind not in ARTIFACT_KINDS:
            raise ValueError("Unknown artifact kind")
        if type(self.charges) is not int or not 0 <= self.charges <= 3:
            raise ValueError("Invalid artifact charges")
        if self.kind != "ancient_relic" and self.charges:
            raise ValueError("Only ward relics have charges")
        if self.maker_id is not None:
            identifier(self.maker_id, "artifact maker")
        if self.creation_year is not None and type(self.creation_year) is not int:
            raise ValueError("Invalid artifact creation year")
        for value in (self.material, self.purpose, self.inscription):
            if not isinstance(value, str):
                raise ValueError("Artifact text must be a string")
        for reference in (self.inscription_language, self.inscription_stage):
            if reference is not None:
                identifier(reference, "inscription reference")
        for operation in self.history:
            identifier(operation, "artifact history operation")

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result.update(owner=self.owner.to_dict() if self.owner else None, custodian=self.custodian.to_dict(),
                      history=list(self.history))
        for key in ("maker_id", "creation_year", "material", "purpose", "inscription",
                    "inscription_language", "inscription_stage"):
            if result[key] is None or result[key] == "":
                del result[key]
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        values = dict(data)
        values["custodian"] = AssetRef.from_dict(values["custodian"])
        values["owner"] = AssetRef.from_dict(values["owner"]) if values.get("owner") else None
        values["history"] = tuple(values.get("history", []))
        return cls(**values)

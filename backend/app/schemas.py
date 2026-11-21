from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    athlete_id: Optional[str] = None
    message: Optional[str] = Field(default=None, max_length=2000)
    # Solo demo/test: simula un guasto per mostrare la modalità di riserva (test T4).
    simulate_failure: Optional[Literal["wearable", "knowledge", "llm"]] = None


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class AthleteRegistrationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    name: str = Field(min_length=1, max_length=120)
    profile: Literal["standard", "paralympic", "master"] = "standard"


class SeedRequest(BaseModel):
    athlete_id: str = Field(default="atleta-demo", min_length=1, max_length=64)
    name: str = "Giulia Ricci"
    profile: Literal["standard", "paralympic", "master"] = "standard"
    scenario: Literal["normal", "overload", "hrv_drop", "recovery"] = "normal"
    seed: int = 7
    consent_data: Optional[bool] = None
    consent_alerts: Optional[bool] = None


class WearableSyncRequest(BaseModel):
    scenario: Literal["normal", "overload", "hrv_drop", "recovery"] = "normal"
    seed: int = Field(default=7, ge=0, le=2_147_483_647)


class ConsentUpdate(BaseModel):
    consent_data: Optional[bool] = None
    consent_alerts: Optional[bool] = None


class AthleteProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    profile: Optional[Literal["standard", "paralympic", "master"]] = None


class DecisionIn(BaseModel):
    decision: Literal["approve", "modify", "reject"]
    reviewer: str = "Dott. Demo"
    note: Optional[str] = None
    final_text: Optional[str] = None

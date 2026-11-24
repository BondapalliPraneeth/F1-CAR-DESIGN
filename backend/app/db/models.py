"""SQLAlchemy ORM models (PostgreSQL in production, SQLite for local/tests)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class CarModel(Base):
    __tablename__ = "car_models"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    asset_path: Mapped[str] = mapped_column(String(256), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    components: Mapped[list[CarComponent]] = relationship(back_populates="car_model", cascade="all, delete-orphan")


class CarComponent(Base):
    __tablename__ = "car_components"
    __table_args__ = (UniqueConstraint("car_model_id", "key", name="uq_component_key_per_model"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    car_model_id: Mapped[int] = mapped_column(ForeignKey("car_models.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)  # stable mesh/component identifier
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    mesh_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    car_model: Mapped[CarModel] = relationship(back_populates="components")
    specifications: Mapped[list[ComponentSpecification]] = relationship(back_populates="component", cascade="all, delete-orphan")


class ComponentSpecification(Base):
    __tablename__ = "component_specifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("car_components.id", ondelete="CASCADE"), index=True)
    parameter: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="model_assumption")
    component: Mapped[CarComponent] = relationship(back_populates="specifications")


class DamageScenario(Base):
    __tablename__ = "damage_scenarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    damages: Mapped[list] = mapped_column(JSON, nullable=False)


class DamageSimulation(Base):
    __tablename__ = "damage_simulations"
    __table_args__ = (Index("ix_damage_simulations_session_created", "session_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_id: Mapped[int | None] = mapped_column(ForeignKey("damage_scenarios.id", ondelete="SET NULL"), nullable=True)
    damages: Mapped[list] = mapped_column(JSON, nullable=False)
    assumptions: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    aero: Mapped[AerodynamicResult | None] = relationship(back_populates="simulation", cascade="all, delete-orphan", uselist=False)
    performance: Mapped[VehiclePerformance | None] = relationship(back_populates="simulation", cascade="all, delete-orphan", uselist=False)
    health: Mapped[list[ComponentHealthRecord]] = relationship(back_populates="simulation", cascade="all, delete-orphan")


class ComponentHealthRecord(Base):
    __tablename__ = "component_health"
    __table_args__ = (
        CheckConstraint("health_pct >= 0 AND health_pct <= 100", name="ck_health_range"),
        Index("ix_component_health_sim_component", "simulation_id", "component_key"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("damage_simulations.id", ondelete="CASCADE"))
    component_key: Mapped[str] = mapped_column(String(64), nullable=False)
    health_pct: Mapped[float] = mapped_column(Float, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)
    damage_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    simulation: Mapped[DamageSimulation] = relationship(back_populates="health")


class AerodynamicResult(Base):
    __tablename__ = "aerodynamic_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("damage_simulations.id", ondelete="CASCADE"), unique=True)
    reference_speed_kmh: Mapped[float] = mapped_column(Float)
    downforce_n: Mapped[float] = mapped_column(Float)
    drag_n: Mapped[float] = mapped_column(Float)
    cl: Mapped[float] = mapped_column(Float)
    cd: Mapped[float] = mapped_column(Float)
    lift_to_drag: Mapped[float] = mapped_column(Float)
    front_balance_pct: Mapped[float] = mapped_column(Float)
    ride_height_mm: Mapped[float] = mapped_column(Float)
    simulation: Mapped[DamageSimulation] = relationship(back_populates="aero")


class VehiclePerformance(Base):
    __tablename__ = "vehicle_performance"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("damage_simulations.id", ondelete="CASCADE"), unique=True)
    lap_time_s: Mapped[float] = mapped_column(Float)
    delta_lap_s: Mapped[float] = mapped_column(Float)
    top_speed_kmh: Mapped[float] = mapped_column(Float)
    performance_index_pct: Mapped[float] = mapped_column(Float)
    overall_health_pct: Mapped[float] = mapped_column(Float)
    brake_temp_front_peak_c: Mapped[float] = mapped_column(Float)
    coolant_temp_mean_c: Mapped[float] = mapped_column(Float)
    retire_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    simulation: Mapped[DamageSimulation] = relationship(back_populates="performance")


class SimulationHistory(Base):
    __tablename__ = "simulation_history"
    __table_args__ = (Index("ix_simulation_history_session_created", "session_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("damage_simulations.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (Index("ix_ai_conversations_session_created", "session_id", "created_at"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EngineeringReport(Base):
    __tablename__ = "engineering_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    simulation_id: Mapped[str] = mapped_column(ForeignKey("damage_simulations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

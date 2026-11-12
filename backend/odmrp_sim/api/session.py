"""Single-process simulation session shared by REST and WebSocket."""

from __future__ import annotations

import asyncio
from pathlib import Path

from odmrp_sim.model.params import ProtocolParams
from odmrp_sim.services.messaging import MessagingService
from odmrp_sim.services.scenarios import load_scenario
from odmrp_sim.sim.engine import SimMode, SimulationEngine

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = REPO_ROOT / "scenarios"


class Session:
    def __init__(self) -> None:
        self.engine = SimulationEngine()
        self.messaging = MessagingService(self.engine)
        self._runner: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self.ws_clients: set = set()
        self.scenario_name: str | None = None

    async def load_named_scenario(self, name: str) -> dict:
        """Pause, load scenario YAML, schedule script ops, leave paused at t=0."""
        await self.pause()
        path = SCENARIOS / f"{name}.yaml"
        async with self._lock:
            # Fresh messaging so delivery-report state does not leak across loads.
            self.messaging = MessagingService(self.engine)
            data = load_scenario(self.engine, path, self.messaging)
            self.scenario_name = name
            # Do not run_until here — script fires when Play/step advances time.
            return data

    async def load_basic_mesh(self) -> dict:
        return await self.load_named_scenario("basic-mesh")

    async def step(self, dt: float) -> dict:
        async with self._lock:
            if self.engine.mode == SimMode.RUNNING:
                raise RuntimeError("paused only")
            self.engine.step(dt)
            return self.engine.snapshot()

    async def run(self) -> None:
        self.engine.mode = SimMode.RUNNING
        self.engine.bus.emit(self.engine.scheduler.now, -1, "sim", op="run")
        if self._runner is None or self._runner.done():
            self._runner = asyncio.create_task(self._run_loop())

    async def pause(self) -> None:
        self.engine.mode = SimMode.PAUSED
        self.engine.bus.emit(self.engine.scheduler.now, -1, "sim", op="pause")
        if self._runner and not self._runner.done():
            self._runner.cancel()
            try:
                await self._runner
            except asyncio.CancelledError:
                pass
            self._runner = None

    async def reset(self) -> None:
        """Pause, clear engine, and reload the current scenario at t=0 (script scheduled only)."""
        await self.pause()
        name = self.scenario_name
        async with self._lock:
            if name:
                path = SCENARIOS / f"{name}.yaml"
                if path.exists():
                    self.messaging = MessagingService(self.engine)
                    load_scenario(self.engine, path, self.messaging)
                    self.scenario_name = name
                    return
            self.engine.reset(seed=self.engine.seed, params=self.engine.params)
            self.messaging = MessagingService(self.engine)

    async def _run_loop(self) -> None:
        try:
            while self.engine.mode == SimMode.RUNNING:
                async with self._lock:
                    # Bail if reset/load flipped mode while we waited for the lock.
                    if self.engine.mode != SimMode.RUNNING:
                        break
                    dt = 0.020 * self.engine.speed
                    self.engine.step(dt)
                await asyncio.sleep(0.020)
        except asyncio.CancelledError:
            return

    def set_params(self, params: ProtocolParams) -> None:
        self.engine.reset(seed=self.engine.seed, params=params)
        self.messaging = MessagingService(self.engine)


session = Session()

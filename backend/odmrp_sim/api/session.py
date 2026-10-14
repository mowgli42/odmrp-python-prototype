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

    async def load_basic_mesh(self) -> dict:
        async with self._lock:
            path = SCENARIOS / "basic-mesh.yaml"
            data = load_scenario(self.engine, path, self.messaging)
            # Settle flood
            self.engine.run_until(self.engine.scheduler.now + 0.5)
            return data

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
        await self.pause()
        async with self._lock:
            self.engine.reset(seed=self.engine.seed, params=self.engine.params)
            self.messaging = MessagingService(self.engine)

    async def _run_loop(self) -> None:
        try:
            while self.engine.mode == SimMode.RUNNING:
                async with self._lock:
                    dt = 0.020 * self.engine.speed
                    self.engine.step(dt)
                await asyncio.sleep(0.020)
        except asyncio.CancelledError:
            return

    def set_params(self, params: ProtocolParams) -> None:
        self.engine.reset(seed=self.engine.seed, params=params)
        self.messaging = MessagingService(self.engine)


session = Session()

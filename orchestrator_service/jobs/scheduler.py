"""
Scheduler simple para jobs periódicos usando asyncio.
Se integra con el evento startup de FastAPI.

CLINICASV1.0 - Sistema de Tareas Programadas
"""

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Callable, Coroutine, Any
import signal

logger = logging.getLogger(__name__)


class JobScheduler:
    """Scheduler simple para ejecutar jobs periódicos."""

    def __init__(self):
        self.tasks = []
        self.running = False
        self._running_tasks: list[asyncio.Task] = []

    async def start(self):
        """Inicia el scheduler y todos los jobs registrados."""
        if self.running:
            logger.warning("⚠️ Scheduler ya está ejecutándose")
            return

        logger.info("🚀 Iniciando JobScheduler...")
        self.running = True

        # Registrar handler para shutdown graceful
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Iniciar todos los jobs
        for task_func, interval_seconds, run_at_startup in self.tasks:
            if run_at_startup:
                t = asyncio.create_task(task_func(), name=f"job-startup-{task_func.__name__}")
                self._running_tasks.append(t)

            # Programar ejecución periódica
            t = asyncio.create_task(
                self._run_periodic(task_func, interval_seconds),
                name=f"job-periodic-{task_func.__name__}",
            )
            self._running_tasks.append(t)

        logger.info(f"✅ JobScheduler iniciado con {len(self.tasks)} jobs")

    async def stop(self):
        """Detiene el scheduler de forma graceful — solo cancela sus propias tasks."""
        if not self.running:
            return

        logger.info("🛑 Deteniendo JobScheduler...")
        self.running = False

        # Solo cancelar las tasks que el scheduler creó
        for task in self._running_tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*self._running_tasks, return_exceptions=True)
        self._running_tasks.clear()
        logger.info("✅ JobScheduler detenido")
    
    def add_job(self, task_func: Callable[[], Coroutine[Any, Any, None]], 
                interval_seconds: int, run_at_startup: bool = False):
        """
        Registra un job para ejecución periódica.
        
        Args:
            task_func: Función async a ejecutar
            interval_seconds: Intervalo en segundos entre ejecuciones
            run_at_startup: Si se ejecuta inmediatamente al iniciar
        """
        self.tasks.append((task_func, interval_seconds, run_at_startup))
        logger.info(f"📋 Job registrado: {task_func.__name__} cada {interval_seconds}s")
    
    async def _run_periodic(self, task_func: Callable[[], Coroutine[Any, Any, None]],
                           interval_seconds: int):
        """Ejecuta una función periódicamente."""
        if interval_seconds <= 0:
            return  # Daily tasks manage their own loop via schedule_daily_at
        while self.running:
            try:
                await asyncio.sleep(interval_seconds)
                if self.running:
                    logger.debug(f"⏰ Ejecutando job: {task_func.__name__}")
                    await task_func()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error en job {task_func.__name__}: {e}")
                # Esperar antes de reintentar
                await asyncio.sleep(min(300, interval_seconds))  # Máximo 5 minutos


# Instancia global del scheduler
scheduler = JobScheduler()


def schedule_daily_at(hour: int, minute: int = 0, second: int = 0):
    """
    Decorador para programar un job diario a una hora específica.
    
    Args:
        hour: Hora del día (0-23)
        minute: Minuto (0-59)
        second: Segundo (0-59)
    """
    def decorator(task_func: Callable[[], Coroutine[Any, Any, None]]):
        async def scheduled_task():
            """Task que calcula el próximo tiempo de ejecución y se auto-reprograma."""
            while True:
                now = datetime.now()
                target_time = time(hour, minute, second)

                # Calcular segundos hasta la próxima ejecución
                if now.time() < target_time:
                    target_datetime = datetime.combine(now.date(), target_time)
                else:
                    target_datetime = datetime.combine(now.date() + timedelta(days=1), target_time)

                seconds_until_target = (target_datetime - now).total_seconds()

                logger.info(f"⏰ {task_func.__name__} programado para {target_datetime.strftime('%Y-%m-%d %H:%M:%S')} "
                          f"(en {seconds_until_target:.0f} segundos)")

                await asyncio.sleep(seconds_until_target)
                try:
                    await task_func()
                except Exception as e:
                    logger.error(f"❌ Error en job diario {task_func.__name__}: {e}")

        # Registrar como run_at_startup para que el scheduler lo lance una vez.
        # El loop interno de scheduled_task se encarga de la re-programación.
        # interval_seconds=0 indica que _run_periodic NO debe lanzarlo de nuevo.
        scheduler.tasks.append((scheduled_task, 0, True))

        return task_func

    return decorator


async def start_scheduler():
    """Función para iniciar el scheduler desde main.py"""
    await scheduler.start()


async def stop_scheduler():
    """Función para detener el scheduler desde main.py"""
    await scheduler.stop()
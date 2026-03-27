import os
import sys
import time
import threading
import queue
import yaml
import json
import platform
import signal
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# 1. Load Environment & Setup Logging
load_dotenv()
from core.structured_logger import setup_logging, get_logger, FORENSIC, verify_log_chain
from core.secure_config import secure_config
from core.privilege_manager import privilege_manager
from core.watchdog import watchdog
from core.performance_monitor import perf
from core.health_api import start_health_api
from core.alert_deduplication import deduplicator
from core.evidence_chain import verify_manifest, generate_manifest

log_dir = Path("evidence/logs")
setup_logging(log_dir)
logger = get_logger("nexus_v5")

# Thread-safe primitives
class GlobalState:
    def __init__(self):
        self.detections_count = 0
        self.incidents_count = 0
        self.monitoring_active = threading.Event()
        self.monitoring_active.set()
        self.start_time = time.time()
        self._lock = threading.Lock()

    def increment_detections(self):
        with self._lock:
            self.detections_count += 1
            return self.detections_count

    def increment_incidents(self):
        with self._lock:
            self.incidents_count += 1
            return self.incidents_count

    def get_counts(self):
        with self._lock:
            return self.detections_count, self.incidents_count

state = GlobalState()

class CircuitBreaker:
    """Prevents repeated API failures from blocking the system"""
    def __init__(self, failure_threshold=5, timeout=60):
        self.failures = 0
        self.threshold = failure_threshold
        self.timeout = timeout
        self.opened_at = None
    
    def call(self, func, *args, **kwargs):
        if self.opened_at and (time.time() - self.opened_at) < self.timeout:
            logger.warning("Circuit breaker is OPEN. Fast-failing API call.")
            raise Exception("Circuit breaker OPEN")
        
        try:
            result = func(*args, **kwargs)
            self.failures = 0
            self.opened_at = None
            return result
        except Exception as e:
            self.failures += 1
            if self.failures >= self.threshold:
                logger.error(f"Circuit breaker threshold {self.threshold} reached. OPENING circuit.")
                self.opened_at = time.time()
            raise

def heartbeat_thread(interval=60):
    """Periodic health beacon to disk for external monitoring"""
    while state.monitoring_active.is_set():
        try:
            hb_path = Path('evidence/.heartbeat')
            det, inc = state.get_counts()
            with open(hb_path, 'w') as f:
                f.write(f"timestamp={datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"detections={det}\n")
                f.write(f"incidents={inc}\n")
                f.write(f"status=ACTIVE\n")
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
        time.sleep(interval)

# Shared queue bridge for narrative engine
class NarrativeQueueBridge:
    def __init__(self):
        from queue import Queue
        self.ntfs_queue = Queue()
        self.entropy_queue = Queue()
        self.behavior_queue = Queue()
        self.process_queue = Queue()

narrative_queues = NarrativeQueueBridge()

def print_banner():
    # Keep banner for console visibility but also log it
    banner = [
        "=" * 80,
        "      SHADOWNET NEXUS v5.0 - UNIFIED FORENSIC INTELLIGENCE",
        "      First-of-its-Kind Live Artifact Synthesis Engine",
        "=" * 80
    ]
    for line in banner:
        print(line)
    logger.info("ShadowNet Nexus v5.0 Started", extra={"event": "STARTUP"})

def run_main_loop(stop_event: threading.Event) -> None:
    """Entry point for both direct execution and service execution."""
    # 0. System Integrity & Hardening
    print_banner()
    
    api_key = secure_config.get_api_key('GEMINI_API_KEY')
    if not api_key:
        logger.error("GEMINI_API_KEY not found in secure store or .env", extra={"event": "CONFIG_ERROR"})
        return

    # 1. Verify Evidence Chain from Previous Sessions
    logger.info("Verifying existing evidence manifests...", extra={"event": "INTEGRITY_CHECK"})
    evidence_path = Path("./evidence/emergency_snapshots")
    if evidence_path.exists():
        for snap_dir in evidence_path.glob("SNAP-*"):
            if snap_dir.is_dir():
                v_res = verify_manifest(snap_dir)
                if v_res["status"] == "TAMPERED":
                    logger.critical(f"Evidence Tamper Detected: {snap_dir.name}", extra={"event": "TAMPER_ALERT", "data": v_res})
    
    l_res = verify_log_chain(log_dir / "forensic_findings.jsonl")
    if l_res["status"] == "TAMPERED":
        logger.critical("Forensic Log Tamper Detected!", extra={"event": "LOG_TAMPER_ALERT", "data": l_res})

    # 2. Import Frozen v4.0 Components
    logger.info("Loading v4.0 core modules...", extra={"event": "LOAD_V4"})
    from core.process_monitor import ProcessMonitor
    from core.proactive_evidence_collector import ProactiveEvidenceCollector
    from core.gemini_command_analyzer import GeminiCommandAnalyzer
    from core.siem_integration import SIEMIntegration, SIEMPlatform
    from core.alert_manager import AlertManager, AlertChannel, AlertSeverity
    from core.gemini_report_generator import GeminiReportGenerator
    from core.incident_report_generator import IncidentReportGenerator
    from core.gemini_behavior_analyzer import GeminiBehaviorAnalyzer
    from core.behavior_monitor import BehavioralMonitor
    from core.emergency_snapshot import EmergencySnapshotEngine

    # 3. Import New v5.0 Modules
    logger.info("Injecting v5.0 forensic modules...", extra={"event": "LOAD_V5"})
    from core.ntfs_artifact_parser import NTFSArtifactParser
    from core.entropy_map_scanner import EntropyMapScanner
    from core.realtime_behavior_monitor import RealtimeBehaviorMonitor
    from core.forensic_narrative_engine import ForensicNarrativeEngine
    from core.file_integrity_monitor import FileIntegrityMonitor

    # 4. Integrate Evidence Chain via Monkey-Patching
    _original_emergency_snapshot = EmergencySnapshotEngine.emergency_snapshot

    def patched_emergency_snapshot(self, threat_type, command, process_info):
        snapshot_id = _original_emergency_snapshot(self, threat_type, command, process_info)
        snapshot_dir = self.snapshots_dir / snapshot_id
        logger.info(f"Signing evidence snapshot: {snapshot_id}", extra={"event": "SNAPSHOT_SIGNED", "data": {"id": snapshot_id}})
        generate_manifest(snapshot_dir)
        return snapshot_id

    EmergencySnapshotEngine.emergency_snapshot = patched_emergency_snapshot

    # 5. Load v5.0 Configuration
    config_path = Path(__file__).parent / 'config' / 'config_v5.yaml'
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.critical(f"Failed to load config: {e}", extra={"event": "CONFIG_ERROR", "data": {"error": str(e)}})
        return

    monitoring_config = config['shadownet']['monitoring']
    keywords = monitoring_config.get('suspicious_keywords', [])

    # 6. Initialize Core Systems (Unified v4.0 + v5.0)
    evidence_collector = ProactiveEvidenceCollector(
        evidence_vault_path="./evidence", 
        enabled=True, 
        capture_network=monitoring_config.get('enable_network_monitoring', True),
        suspicious_keywords=keywords
    )
    alert_mgr = AlertManager(config=config['shadownet']['alerting'])
    siem_mgr = SIEMIntegration(config=config['shadownet']['siem'])
    
    ai_analyzer = GeminiCommandAnalyzer(api_key, suspicious_keywords=keywords)
    behavior_ai_analyzer = GeminiBehaviorAnalyzer(api_key)
    incident_reporter = IncidentReportGenerator(evidence_path="./evidence")
    
    incident_queue = queue.Queue(maxsize=1000)
    
    cb = CircuitBreaker(failure_threshold=5, timeout=60)
 
    # V4 Behavioral Monitor (simulation-based, uses GeminiBehaviorAnalyzer)
    def v4_behavior_alert_callback(alert_data: dict):
        if deduplicator.should_alert("V4_BEHAVIOR", alert_data):
            logger.log(FORENSIC, "V4 Behavioral Anomaly", extra={"event": "V4_BEHAVIOR", "data": alert_data})
            try:
                incident_queue.put({
                    "type": "behavioral_v4",
                    "command": alert_data.get("command", ""),
                    "process_info": alert_data.get("process_info", {}),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "snapshot_id": "N/A"
                }, block=False)
                state.increment_incidents()
            except queue.Full:
                logger.error("Incident queue overflow - dropping behavioral alert")
    
    v4_behavior_monitor = BehavioralMonitor(
        analyzer=behavior_ai_analyzer,
        callback=v4_behavior_alert_callback,
        enable_simulation=config['shadownet']['monitoring'].get('enable_behavioral_simulation', False)
    )
    v4_behavior_monitor.start_monitoring()

    # 7. Bridge v5.0 findings to v4.0 Reporting (FIX FOR REAL-TIME UTILIZATION)
    def v4_bridge_callback(finding):
        """Allows v5 modules to trigger v4 reports/snapshots."""
        try:
            # Add timestamp if missing
            if 'timestamp' not in finding:
                finding['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # If it's a v5 finding (NTFS/Entropy), command might be a description
            cmd = finding.get('command') or finding.get('description', 'SYSTEM_ANOMALY')
            proc = finding.get('process_info') or {
                'name': 'KERNEL_SPACE', 
                'pid': 0, 
                'user': 'SYSTEM',
                'timestamp': finding['timestamp']
            }
            
            # Already has snapshot_id? If not, capture now.
            snapshot_id = finding.get('snapshot_id')
            if not snapshot_id or snapshot_id == 'N/A':
                res = evidence_collector.on_threat_detected({
                    'command': cmd,
                    'process_info': proc,
                    'category': finding.get('verdict', 'v5_detection')
                })
                snapshot_id = res.get('snapshot_id', 'N/A')
            
            unified_finding = {
                'type': finding.get('type', 'v5_detection'),
                'command': cmd,
                'process_info': proc,
                'timestamp': finding['timestamp'],
                'snapshot_id': snapshot_id
            }
            
            incident_queue.put(unified_finding, block=False)
            state.increment_incidents()
        except Exception as e:
            logger.error(f"V4 Bridge Error: {e}")

    # Background Work Engine (THE V4 BRIDGE)
    def v4_log_worker():
        """Background thread for AI analysis, reports, and SIEM."""
        while not stop_event.is_set():
            try:
                finding = incident_queue.get(timeout=1)
                if finding is None:
                    incident_queue.task_done()
                    break
                
                command = finding['command']
                proc = finding['process_info']
                snapshot_id = finding.get('snapshot_id', 'N/A')
                finder_type = finding.get('type', 'suspicious_activity')
                
                try:
                    ai_res = cb.call(ai_analyzer.analyze_command, command, proc)
                except Exception as e:
                    logger.warning(f"AI Analysis Failed (Circuit Breaker or API): {e}")
                    # Directly trigger the standardized fallback logic that preserves V5 state
                    ai_res = ai_analyzer._keyword_fallback(command, str(e), proc)
                    
                    # Ensure legacy compatibility fields are mapped
                    ai_res['category'] = finding.get('verdict', finder_type)
                    
                    if proc.get('name') == 'KERNEL_SPACE':
                        ai_res['confidence'] = finding.get('confidence', 0.90)
                        
                        # Pack the original evidence chain into the explanation if it exists
                        evidence = finding.get('evidence_chain')
                        if evidence:
                            ai_res['explanation'] += f"\nRaw Evidence: {', '.join(evidence) if isinstance(evidence, list) else evidence}"
                
                finding['ai_analysis'] = ai_res
                
                # Professional reporting for all system detections (Process + NTFS + Entropy)
                # Generate Markdown Report (V4 logic renamed to incident.md)
                try:
                    report_path = incident_reporter.generate_incident_report({
                        'incident_id': f"INC-{int(time.time())}",
                        'threat_type': ai_res.get('category', finder_type),
                        'command': command,
                        'process_info': proc,
                        'snapshot_id': snapshot_id,
                        'detection_time': finding['timestamp'],
                        'ai_analysis': ai_res,
                        'severity': ai_res.get('severity', 'HIGH')
                    })
                    logger.info(f"Report generated: {report_path}", extra={"event": "REPORT_READY", "id": snapshot_id})
                except Exception as e:
                    logger.error(f"Report generation failed: {e}")

                # Send to SIEM (V4 logic)
                if config['shadownet']['siem']['enable_siem']:
                    siem_mgr.send_event({
                        'type': 'forensic_alert',
                        'command': command,
                        'process': proc.get('name'),
                        'severity': ai_res.get('severity', 'HIGH'),
                        'confidence': ai_res.get('confidence', 0)
                    })

                incident_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker Error: {e}")

    worker_thread = threading.Thread(target=v4_log_worker, daemon=True, name="V4Bridge")
    worker_thread.start()

    def v5_behavior_callback(analysis):
        if deduplicator.should_alert("BEHAVIOR_ALERT", analysis):
            logger.log(FORENSIC, f"Behavioral Anomaly: {analysis['verdict']}", extra={"event": "BEHAVIOR_ALERT", "data": analysis})
            narrative_queues.behavior_queue.put(analysis)
            state.increment_incidents()
            alert_mgr.send_alert(
                title=f"Behavioral Anomaly: {analysis['verdict']}",
                message=f"Rules triggered: {', '.join(analysis['triggered_rules'])}",
                severity=AlertSeverity.HIGH if "CONFIRMED" in analysis['verdict'] else AlertSeverity.MEDIUM,
                channels=[AlertChannel.CONSOLE],
                metadata=analysis
            )

    # 8. Detection Handlers
    def on_suspicious_command(command: str, process_info: dict):
        my_pid = os.getpid()
        if process_info.get('pid') == my_pid or process_info.get('parent_pid') == my_pid:
            return

        creation_time_str = process_info.get('timestamp')
        if creation_time_str:
            try:
                creation_time = datetime.fromisoformat(creation_time_str)
                lag_ms = (datetime.now(timezone.utc) - creation_time).total_seconds() * 1000
                logger.debug(f"Process detection lag: {lag_ms:.2f}ms")
            except: pass

        if deduplicator.should_alert("PROCESS_ALERT", {"cmd": command, "proc": process_info['name']}):
            logger.log(FORENSIC, f"v4.0 DETECTION: {process_info.get('name')}", extra={"event": "PROCESS_ALERT", "data": {"command": command, "process": process_info}})
            state.increment_detections()
            res = evidence_collector.on_threat_detected({'command': command, 'process_info': process_info})
            finding = {
                "type": "process_alert",
                "command": command,
                "process_info": process_info,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "snapshot_id": res.get('snapshot_id', 'N/A')
            }
            narrative_queues.process_queue.put(finding)
            try:
                incident_queue.put(finding, block=False)
                state.increment_incidents()
            except queue.Full:
                logger.error("Incident queue overflow - dropping process alert")

    # Start Active Monitors
    if monitoring_config.get('enable_process_monitoring', True):
        monitor = ProcessMonitor(callback=on_suspicious_command, suspicious_keywords=keywords)
        monitor.start_monitoring()

    fim = None
    if monitoring_config.get('enable_file_monitoring', True):
        fim = FileIntegrityMonitor(config, callback=v4_bridge_callback)
        fim.start_monitoring()

    # 9. Startup & Watchdog Registration
    start_health_api(port=8765)
    # Operational Health Dashboard (Dim 6)
    db_config = config.get('dashboard', {})
    if db_config.get('enabled', True):
        from core.dashboard import start_dashboard
        start_dashboard(
            state,
            host=db_config.get('host', '127.0.0.1'),
            port=db_config.get('port', 8000)
        )

    # Factory wrappers
    def ntfs_factory():
        p = NTFSArtifactParser(config, evidence_collector=evidence_collector, alert_mgr=alert_mgr)
        p.incident_callback = v4_bridge_callback # Inject bridge
        p.narrative_queue = narrative_queues.ntfs_queue
        p.running = True
        return p

    def entropy_factory():
        s = EntropyMapScanner(config, evidence_collector=evidence_collector, alert_mgr=alert_mgr)
        s.incident_callback = v4_bridge_callback # Inject bridge
        s.narrative_queue = narrative_queues.entropy_queue
        s.running = True
        return s

    def narrative_factory():
        engine = ForensicNarrativeEngine(config, api_key)
        engine.ntfs_queue = narrative_queues.ntfs_queue
        engine.entropy_queue = narrative_queues.entropy_queue
        engine.behavior_queue = narrative_queues.behavior_queue
        engine.process_queue = narrative_queues.process_queue
        return engine

    def behavior_factory():
        old = watchdog._registry.get("behavior_monitor", {}).get("thread")
        if old and hasattr(old, 'stop'):
            old.stop()
        return RealtimeBehaviorMonitor(config, v5_behavior_callback)

    if not privilege_manager.can_do("raw_disk_read"):
        logger.warning(
            "Not running as admin/root. NTFS parser and entropy scanner disabled.",
            extra={"event": "PRIVILEGE_WARNING"})
        can_do_disk = False
    else:
        logger.info("Admin/root confirmed. All v5.0 modules active.", extra={"event": "PRIVILEGE_OK"})
        can_do_disk = True

    if config['shadownet_v5']['ntfs_parser']['enabled'] and can_do_disk:
        watchdog.register("ntfs_parser", ntfs_factory, heartbeat_timeout=60.0)
        
    if config['shadownet_v5']['entropy_scanner']['enabled'] and can_do_disk:
        watchdog.register("entropy_scanner", entropy_factory, heartbeat_timeout=360.0)
        
    if config['shadownet_v5']['realtime_behavior']['enabled']:
        watchdog.register("behavior_monitor", behavior_factory, heartbeat_timeout=120.0)
        
    watchdog.register("narrative_engine", narrative_factory, heartbeat_timeout=120.0)
    
    watchdog.register(
        "system_main",
        lambda: threading.current_thread(),
        heartbeat_timeout=10.0,
        max_restarts=0
    )
    
    process_monitor = ProcessMonitor(callback=on_suspicious_command, suspicious_keywords=keywords)
    process_monitor.start_monitoring()
    
    def shutdown_handler(signum, frame):
        logger.info(f"Signal {signum} received. Initiating graceful shutdown...")
        state.monitoring_active.clear()
        stop_event.set()
        
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    watchdog.start()
    logger.info("ShadowNet Nexus v5.0 Hardening Complete. Monitoring active.", extra={"event": "LIFECYCLE"})

    # 10. Main Loop
    try:
        while not stop_event.is_set():
            time.sleep(1)
            ts = int(time.time())
            watchdog.heartbeat("system_main")
            
            if ts % 600 == 0:
                perf.write_report(Path("evidence/reports"))
            
            if ts % 60 == 0:
                det, inc = state.get_counts()
                stats = {
                    "threads": watchdog.status(),
                    "queue_depth": incident_queue.qsize(),
                    "detections": det,
                    "incidents": inc
                }
                logger.info("System health update", extra={"event": "HEALTH_UPDATE", "data": stats})
                
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        state.monitoring_active.clear()
        logger.info("Initiating Secure Shutdown...", extra={"event": "SHUTDOWN_START"})
        
        try: watchdog.stop()
        except: pass

        try: process_monitor.stop_monitoring()
        except: pass

        try:
            incident_queue.put(None, block=False)
            worker_thread.join(timeout=5)
        except: pass

        try:
            if fim is not None:
                fim.stop_monitoring()
        except: pass

        try:
            if 'v4_behavior_monitor' in locals():
                v4_behavior_monitor.stop_monitoring()
        except: pass

        try: verify_log_chain(log_dir / "forensic_findings.jsonl")
        except: pass

        logger.info("ShadowNet Nexus v5.0 shutdown complete", extra={"event": "SHUTDOWN_COMPLETE"})

if __name__ == "__main__":
    stop = threading.Event()
    try:
        run_main_loop(stop_event=stop)
    except KeyboardInterrupt:
        logger.info("Interrupt received, shutting down...")
        stop.set()
    except Exception as e:
        logger.critical(f"Unhandled system crash: {e}", exc_info=True)
        stop.set()

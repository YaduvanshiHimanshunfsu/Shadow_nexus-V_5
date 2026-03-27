 Shadow_nexus-V_5

Real-Time Forensic Intelligence & Anti-Forensics Detection Platform

 Overview

Shadow_nexus-V_5 is a live digital forensic and incident response system that detects malicious activities in real time, captures volatile system evidence, and generates structured forensic insights.

The project was developed during the ISEA Hackathon on 28 February, a 24-hour hackathon where the problem statement was provided at the start.

Within this limited timeframe, the system was designed and implemented to address anti-forensics techniques such as log deletion, file wiping, and timestamp manipulation.

Team Members
Himanshu Yadav
Srikar
KVN Srinitya

Achievement
🥇 1st Prize – ISEA Hackathon
⏱️ Built within 24 hours
🧠 Developed a working prototype solving a real-world cybersecurity challenge

Objective

To build a system capable of:

Detecting suspicious activities during execution
Capturing forensic evidence before it is deleted
Converting raw system events into actionable intelligence

Key Features
1. Real-Time Threat Detection
Monitors system processes and commands
Detects suspicious activities (e.g., log clearing, shadow deletion)
2. File Integrity Monitoring (FIM)
Tracks file creation, deletion, and modification
Works across monitored directories
3. Anti-Forensics Detection
Identifies attempts to:
Delete logs
Wipe files
Manipulate timestamps
4. Emergency Snapshot Engine
Captures system state in <100 ms
Includes:
Running processes
System logs
Network connections
5. Advanced Artifact Analysis
NTFS artifact parsing ($MFT, $USN Journal)
Entropy-based detection for hidden/encrypted data
6. AI-Based Command Analysis
Integrates LLM (Gemini)
Classifies commands as legitimate or malicious
7. Forensic Narrative Generation
Converts multiple alerts into a structured incident timeline
8. Evidence Integrity
Uses SHA-256 hashing
Ensures tamper-proof forensic storage


Detection Modules
   │
   ▼
Incident Queue
   │
   ▼
AI Analysis Engine
   │
   ▼
Emergency Snapshot Engine
   │
   ▼
Evidence Vault & Report Generator



Shadow_nexus-V_5/
│── core/
│   ├── process_monitor.py
│   ├── file_integrity_monitor.py
│   ├── ntfs_artifact_parser.py
│   ├── entropy_map_scanner.py
│   ├── emergency_snapshot.py
│   ├── evidence_vault.py
│   └── forensic_narrative_engine.py
│
│── config/
│   └── config_v5.yaml
│
│── prompts/
│   └── enhanced_prompts.py
│
│── shadownet_nexus_v5.py
│── requirements.txt
│── README.md


Use Cases
Digital Forensics & Incident Response (DFIR)
SOC (Security Operations Center) automation
Cybersecurity research projects
Academic and defense applications

Future Enhancements
Cross-platform kernel-level monitoring
Integration with SIEM tools
Machine learning-based anomaly detection
Real-time visualization dashboard

Conclusion

Shadow_nexus-V_5 demonstrates a shift from post-incident forensics to real-time forensic intelligence, enabling faster detection, evidence preservation, and automated analysis of cyber threats.

# scripts/benchmarks_and_stress_test.py
import asyncio
import time
import uuid
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import httpx
from datetime import datetime
from backend.main import app
from backend.app.config.database import Base, init_db
from backend.app.services.auth_service import AuthService
from backend.app.models.user import UserRoleEnum
from backend.app.services.audit_service import AuditService
from httpx import AsyncClient, ASGITransport

async def run_performance_benchmarks():
    print("=" * 70)
    print("[*] ONIONSETU SYSTEM PERFORMANCE & STRESS BENCHMARKS")
    print("=" * 70)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await init_db()
        token = AuthService.create_access_token(user_id="perf_grader_01", role=UserRoleEnum.GRADER)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. API Load Smoke Test (50 Sequential & Concurrent Requests)
        print("\n[TEST 1/4] Running API Health & Scan List Load Test (50 requests)...")
        start_time = time.time()
        tasks = [client.get("/v1/health") for _ in range(50)]
        responses = await asyncio.gather(*tasks)
        elapsed_api = time.time() - start_time
        success_count = sum(1 for r in responses if r.status_code == 200)
        avg_latency_ms = (elapsed_api / 50) * 1000
        print(f"  -> Completed 50 requests in {elapsed_api:.3f}s (Avg: {avg_latency_ms:.2f}ms/req)")
        print(f"  -> Success Rate: {success_count}/50 ({success_count/50*100:.1f}%)")
        assert success_count == 50, "API load test failed!"

        # 2. Sync Queue Stress Test (100 Offline Records Ingestion)
        print("\n[TEST 2/4] Running Offline Sync Queue Ingestion (100 batched scans)...")
        sample_scans = []
        for i in range(100):
            scan_id = f"stress_scan_{i}_{uuid.uuid4().hex[:8]}"
            sample_scans.append({
                "id": scan_id,
                "lot_number": f"LOT-STRESS-{i:03d}",
                "farmer_name": f"Farmer #{i}",
                "farmer_phone": f"+9198000{i:05d}",
                "procurement_center_id": "APMC-LASALGAON-01",
                "grader_id": "perf_grader_01",
                "sync_status": "pendingOffline",
                "result": {
                    "id": f"res_stress_{uuid.uuid4().hex[:10]}",
                    "grade_a_percentage": 85.0 + (i % 10),
                    "urs_percentage": 15.0 - (i % 10),
                    "average_ai_confidence": 0.93,
                    "policy_version": "v1.0.0",
                    "total_onions_count": 25,
                    "grade_a_count": 22,
                    "damaged_count": 2,
                    "rotten_count": 1,
                    "sprouted_count": 0,
                    "undersized_count": 0,
                    "avg_size_mm": 54.0,
                }
            })

        start_sync = time.time()
        sync_res = await client.post(
            "/v1/sync/batch",
            json={"client_device_id": "perf_tablet_01", "scans": sample_scans},
            headers=headers,
        )
        elapsed_sync = time.time() - start_sync
        assert sync_res.status_code == 200, f"Sync error: {sync_res.text}"
        sync_data = sync_res.json()
        print(f"  -> Ingested {sync_data['processed_count']} offline scans in {elapsed_sync:.3f}s")
        print(f"  -> Throughput: {100 / elapsed_sync:.1f} scans/second")
        assert sync_data['processed_count'] == 100

        # 3. SHA-256 Audit Chain Integrity Check
        print("\n[TEST 3/4] Cryptographic Audit Chain Verification...")
        verify_res = await client.get("/v1/audit/verify", headers=headers)
        assert verify_res.status_code == 200
        audit_data = verify_res.json()
        print(f"  -> Verified {audit_data['total_records_checked']} sequential hash-chain records")
        print(f"  -> Integrity Status: {audit_data['is_valid']} ('{audit_data['message']}')")
        assert audit_data["is_valid"] is True

        # 4. Report PDF Generation Latency
        print("\n[TEST 4/4] PDF Report Generation Performance...")
        start_pdf = time.time()
        pdf_res = await client.get(f"/v1/reports/{sample_scans[0]['id']}/download", headers=headers)
        elapsed_pdf = time.time() - start_pdf
        assert pdf_res.status_code == 200
        print(f"  -> ReportLab compiled complete PDF ({len(pdf_res.content)} bytes) in {elapsed_pdf*1000:.1f}ms (< 5000ms SLA)")
        assert elapsed_pdf < 5.0

    print("\n" + "=" * 70)
    print("[SUCCESS] ALL PERFORMANCE, STRESS & DATA INTEGRITY BENCHMARKS PASSED")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_performance_benchmarks())

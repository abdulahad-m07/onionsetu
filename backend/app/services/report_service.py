# backend/app/services/report_service.py
import io
import os
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from backend.app.schemas.scan import ScanResponse
from backend.app.schemas.batch import BatchAssessmentSchema
from backend.app.config.settings import settings


def build_verification_url(scan_id: str) -> str:
    """Public verification URL encoded in report QR codes.

    Resolves to this deployment's real verification endpoint
    (GET /v1/verify/{scan_id}). Separated for testability; the host comes
    from PUBLIC_BASE_URL so printed reports never carry a dead link.
    """
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/v1/verify/{scan_id}"

class ReportService:
    @staticmethod
    def generate_pdf_report(
        scan: ScanResponse,
        output_path: str = None,
        batch: BatchAssessmentSchema | None = None,
    ) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer if output_path is None else output_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#E65100'),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            'SubTitleStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=12,
        )
        section_style = ParagraphStyle(
            'SectionStyle',
            parent=styles['Heading2'],
            fontSize=13,
            textColor=colors.HexColor('#2E7D32'),
            spaceBefore=10,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#1A1A1A'),
        )

        story = []

        # 1. Header Banner
        story.append(Paragraph("ONIONSETU: DIGITAL QUALITY ASSESSMENT REPORT", title_style))
        story.append(Paragraph(f"Official APMC Procurement Grading Certificate • Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#E65100'), spaceAfter=14))

        # 2. Lot & Farmer Metadata Table
        meta_data = [
            [Paragraph("<b>Lot Number:</b>", body_style), Paragraph(scan.lot_number, body_style),
             Paragraph("<b>Scan ID:</b>", body_style), Paragraph(scan.id[:16], body_style)],
            [Paragraph("<b>Farmer Name:</b>", body_style), Paragraph(scan.farmer_name, body_style),
             Paragraph("<b>Contact:</b>", body_style), Paragraph(scan.farmer_phone, body_style)],
            [Paragraph("<b>Procurement Center:</b>", body_style), Paragraph(scan.procurement_center_id, body_style),
             Paragraph("<b>Grader ID:</b>", body_style), Paragraph(scan.grader_id, body_style)],
        ]
        meta_table = Table(meta_data, colWidths=[1.4 * inch, 2.2 * inch, 1.2 * inch, 2.2 * inch])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F9F9FB')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#E0E0E0')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EAEAEA')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # 3. Overall Quality Grade Card
        res = scan.result
        grade_a_pct = f"{res.grade_a_percentage:.1f}%" if res else "N/A"
        urs_pct = f"{res.urs_percentage:.1f}%" if res else "N/A"
        conf_pct = f"{(res.average_ai_confidence * 100):.1f}%" if res else "N/A"
        policy_ver = res.policy_version if res else "v1.0.0"

        story.append(Paragraph("AI Quality Assessment Summary", section_style))
        grade_data = [
            ["Grade A Percentage", "URS / Undergrade %", "AI Model Confidence", "Policy Standard"],
            [grade_a_pct, urs_pct, conf_pct, policy_ver],
        ]
        grade_table = Table(grade_data, colWidths=[1.75 * inch, 1.75 * inch, 1.75 * inch, 1.75 * inch])
        grade_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E65100')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#FFF3E0')),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 13),
            ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#C62828')),
            ('TEXTCOLOR', (2, 1), (2, 1), colors.HexColor('#1565C0')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#E65100')),
        ]))
        story.append(grade_table)
        story.append(Spacer(1, 14))

        # 4. Defect Breakdown Table
        story.append(Paragraph("Sample Defect Breakdown", section_style))
        total_count = res.total_onions_count if res else 0
        defect_data = [
            ["Defect Category", "Count", "Percentage of Sample", "Grading Impact"],
            ["Grade A (Healthy)", str(res.grade_a_count if res else 0), f"{(res.grade_a_count / max(1, total_count) * 100):.1f}%" if res else "0%", "Accepted"],
            ["Damaged / Bruised", str(res.damaged_count if res else 0), f"{(res.damaged_count / max(1, total_count) * 100):.1f}%" if res else "0%", "Rejection / URS"],
            ["Rotten / Decay", str(res.rotten_count if res else 0), f"{(res.rotten_count / max(1, total_count) * 100):.1f}%" if res else "0%", "Rejection / URS"],
            ["Sprouted", str(res.sprouted_count if res else 0), f"{(res.sprouted_count / max(1, total_count) * 100):.1f}%" if res else "0%", "Rejection / URS"],
            ["Undersized (<40mm)", str(res.undersized_count if res else 0), f"{(res.undersized_count / max(1, total_count) * 100):.1f}%" if res else "0%", "Rejection / URS"],
        ]
        defect_table = Table(defect_data, colWidths=[2.5 * inch, 1.2 * inch, 1.8 * inch, 1.5 * inch])
        defect_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#37474F')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9F9FB')]),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(defect_table)
        story.append(Spacer(1, 14))

        # 4b. Batch-Level Final Grade (A/B/C/Reject) — the ONE product result.
        # Shown only when a validated batch assessment exists; per-onion
        # grades or A/B/C percentages are never displayed (not the product).
        if batch is not None:
            story.append(Paragraph("Batch Final Grade (A / B / C / Reject)", section_style))
            # `sample_size` counts Roboflow view detections, NOT unique onions
            # (the same physical onions recur across views), so the label says
            # exactly that. The assessed batch is the grader-declared count.
            sample_label = f"{batch.sample_size} view detections"
            if batch.sample_size_estimated:
                sample_label += " (estimated*)"
            review_label = "HUMAN REVIEW REQUIRED" if batch.review_required else "No review flag"
            if batch.urs_percent is not None:
                urs_label = (
                    f"URS {batch.urs_percent:.2f}% of "
                    f"{batch.assessed_onions_declared} declared onions"
                )
            else:
                urs_label = "URS unknown — fallback grade, human review"
            batch_data = [
                ["Final Grade", "Assessment Confidence", "Sample", "Review Status"],
                [
                    batch.final_grade.value,
                    f"{(batch.assessment_confidence * 100):.1f}%",
                    sample_label,
                    review_label,
                ],
                ["URS (provisional policy)", "Batch Assessed", "Views Analyzed", "Policy"],
                [
                    urs_label,
                    str(batch.assessed_onions_declared or "n/a"),
                    str(batch.images_analyzed),
                    batch.policy_version,
                ],
            ]
            batch_table = Table(batch_data, colWidths=[1.75 * inch, 1.75 * inch, 1.75 * inch, 1.75 * inch])
            batch_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#E8F5E9')),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 13),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#2E7D32')),
                ('TEXTCOLOR', (0, 2), (-1, 2), colors.white),
                ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 2), (-1, 2), 10),
                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#E8F5E9')),
                ('FONTSIZE', (0, 3), (-1, 3), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#2E7D32')),
            ]))
            story.append(batch_table)
            story.append(Spacer(1, 6))
            story.append(Paragraph(
                f"Policy {batch.policy_version}"
                f"{' (provisional — requires APMC validation)' if 'provisional' in batch.policy_version else ''}"
                f" • Views analyzed: {batch.images_analyzed} • "
                f"Detection: {batch.roboflow_model} • Assessment: {batch.assessment_model}<br/>"
                "*View detections are NOT unique onions: the same physical "
                "onions may appear in multiple views. URS% uses the "
                "grader-declared batch size as its denominator.",
                body_style,
            ))
            story.append(Spacer(1, 14))

        # 5. QR Code & SHA-256 Hash Chain Stamp
        story.append(Paragraph("Tamper-Evident Integrity Stamp", section_style))
        
        # Generate QR code resolving to this deployment's verification API.
        qr = qrcode.QRCode(box_size=4, border=1)
        verification_url = build_verification_url(scan.id)
        qr.add_data(verification_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)

        audit_hash = scan.audit_hash or (res.audit_hash if res else "N/A")
        footer_data = [
            [
                RLImage(qr_buffer, width=1.1 * inch, height=1.1 * inch),
                Paragraph(
                    f"<b>Verification URL:</b> {verification_url}<br/><br/>"
                    f"<b>SHA-256 Audit Hash:</b><br/><font face='Courier' size='8'>{audit_hash}</font><br/><br/>"
                     f"<b>AI Vision Model:</b> Roboflow Hosted Vision Model (server-side inference) + Qwen2.5-VL 72B via OpenRouter Batch Assessment + Deterministic Grading Engine",
                    body_style
                )
            ]
        ]
        footer_table = Table(footer_data, colWidths=[1.4 * inch, 5.6 * inch])
        footer_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#BDBDBD')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(footer_table)

        doc.build(story)
        pdf_data = buffer.getvalue() if output_path is None else b""
        buffer.close()
        return pdf_data

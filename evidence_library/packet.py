"""Build compact evidence packets for SLIPSTREAM consumption."""

from .models import EvidenceRecord, EvidencePacket


def to_packet(record: EvidenceRecord) -> EvidencePacket:
    """Convert a full EvidenceRecord to the smallest useful packet for SLIPSTREAM."""
    return EvidencePacket(
        id=record.id,
        title=record.title,
        source_type=record.source_type,
        date=record.date_published or record.date_added[:10],
        population_topic=record.population_topic,
        key_findings=record.key_findings,
        limitations=record.limitations,
        citation=record.citation,
        confidence_flag=record.confidence_flag,
        recency_flag=record.recency_flag,
        human_review_flag=record.human_review_flag,
        tags=record.tags,
        viability_score=record.viability_score,
    )


def format_packet_for_prompt(packet: EvidencePacket) -> str:
    """
    Render a packet as a compact text block for injection into a SLIPSTREAM prompt.
    Keeps the context window small — no raw content, no full summaries.
    """
    lines = [
        f"## Evidence: {packet.title}",
        f"- Source type: {packet.source_type}",
        f"- Date: {packet.date or 'unknown'}",
    ]
    if packet.population_topic:
        lines.append(f"- Topic/Population: {packet.population_topic}")
    if packet.key_findings:
        lines.append(f"- Key findings: {packet.key_findings}")
    if packet.limitations:
        lines.append(f"- Limitations: {packet.limitations}")
    if packet.citation:
        lines.append(f"- Citation: {packet.citation}")
    if packet.tags:
        lines.append(f"- Tags: {', '.join(packet.tags)}")
    lines.append(f"- Confidence: {packet.confidence_flag} | Recency: {packet.recency_flag}")
    if packet.human_review_flag:
        lines.append("- ⚠ Human review flagged")
    return "\n".join(lines)


def format_multi_packet_context(packets: list[EvidencePacket], query: str = "") -> str:
    """
    Format multiple packets for a SLIPSTREAM context injection.
    Includes a header and separator between items.
    """
    if not packets:
        return f"No evidence found{f' for: {query}' if query else ''}."

    header = f"Evidence Library results ({len(packets)} items){f' for: {query}' if query else ''}:\n"
    blocks = [format_packet_for_prompt(p) for p in packets]
    return header + "\n\n---\n\n".join(blocks)

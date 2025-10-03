from dataclasses import dataclass


@dataclass
class Organization:
    id: int
    name: str
    rub_balance: str
    video_cut_description_end_sample: str
    publication_text_end_sample: str
    tone_of_voice: list[str]
    brand_rules: list[str]
    compliance_rules: list[str]
    audience_insights: list[str]
    products: list[dict]
    locale: dict
    additional_info: list[str]
    created_at: str
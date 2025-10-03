from dataclasses import dataclass


@dataclass
class Publication:
    id: int
    organization_id: int
    category_id: int
    creator_id: int
    moderator_id: int | None

    vk_source: bool | None
    tg_source: bool | None

    text_reference: str
    text: str
    image_fid: str | None
    image_name: str | None

    openai_rub_cost: int

    moderation_status: str | None
    moderation_comment: str | None

    publication_at: str | None
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "category_id": self.category_id,
            "creator_id": self.creator_id,
            "moderator_id": self.moderator_id,
            "vk_source": self.vk_source,
            "tg_source": self.tg_source,
            "text_reference": self.text_reference,
            "text": self.text,
            "image_fid": self.image_fid,
            "image_name": self.image_name,
            "openai_rub_cost": self.openai_rub_cost,
            "moderation_status": self.moderation_status,
            "moderation_comment": self.moderation_comment,
            "publication_at": self.publication_at,
            "created_at": self.created_at,
        }


@dataclass
class Category:
    id: int
    organization_id: int

    name: str
    prompt_for_image_style: str

    goal: str

    # Структура контента
    structure_skeleton: list[str]
    structure_flex_level_min: int
    structure_flex_level_max: int
    structure_flex_level_comment: str

    # Требования к контенту
    must_have: list[str]
    must_avoid: list[str]

    # Правила для соцсетей
    social_networks_rules: str

    # Ограничения по длине
    len_min: int
    len_max: int

    # Ограничения по хештегам
    n_hashtags_min: int
    n_hashtags_max: int

    # Стиль и тон
    cta_type: str
    tone_of_voice: list[str]

    # Бренд и примеры
    brand_rules: list[str]
    good_samples: list[dict]

    # Дополнительная информация
    additional_info: list[str]

    created_at: str

@dataclass
class Autoposting:
    id: int
    organization_id: int

    filter_prompt: str
    rewrite_prompt: str
    tg_channels: list[str]

    created_at: str

@dataclass
class VideoCut:
    id: int
    project_id: int
    organization_id: int
    creator_id: int
    moderator_id: int

    inst_source: bool
    youtube_source: bool

    youtube_video_reference: str
    name: str
    description: str
    transcript: str
    tags: list[str]
    video_fid: str
    video_name: str
    original_url: str

    vizard_rub_cost: int
    moderation_status: str
    moderation_comment: str

    publication_at: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "organization_id": self.organization_id,
            "creator_id": self.creator_id,
            "moderator_id": self.moderator_id,
            "inst_source": self.inst_source,
            "youtube_source": self.youtube_source,
            "youtube_video_reference": self.youtube_video_reference,
            "name": self.name,
            "description": self.description,
            "transcript": self.transcript,
            "tags": self.tags,
            "video_fid": self.video_fid,
            "video_name": self.video_name,
            "original_url": self.original_url,
            "vizard_rub_cost": self.vizard_rub_cost,
            "moderation_status": self.moderation_status,
            "moderation_comment": self.moderation_comment,
            "publication_at": self.publication_at,
            "created_at": self.created_at
        }
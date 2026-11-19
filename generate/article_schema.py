"""뉴스 생성기에서 사용하는 기사 응답 스키마."""

from pydantic import BaseModel, Field, field_validator


# LLM 응답 필드와 길이·문단 수를 검사합니다.
class Draft(BaseModel):
    title: str = Field(min_length=10, max_length=140)
    subtitle: str = Field(min_length=10, max_length=220)
    summary: str = Field(min_length=30, max_length=500)
    paragraphs: list[str] = Field(min_length=5, max_length=9)
    tags: list[str] = Field(min_length=3, max_length=8,
                            description="기사 내용의 핵심 주제·인물·기관 키워드 3~8개")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values):
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(set(cleaned)) != len(cleaned):
            raise ValueError("태그는 비어 있지 않고 중복되지 않아야 합니다.")
        return cleaned

from pydantic import BaseModel


class MemberResponse(BaseModel):
    id: int
    username: str
    role: str

    model_config = {"from_attributes": True}


class HouseholdResponse(BaseModel):
    id: int
    name: str
    slug: str
    invite_code: str
    members: list[MemberResponse]

    model_config = {"from_attributes": True}

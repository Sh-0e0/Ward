"""/정보수정: 바뀐 항목만 반영하는 순수 로직 (디스코드와 무관해서 테스트하기 쉬움)"""
from tiers import has_division, tier_label


def compute_edit(user, tier=None, division=None, main_lane=None, sub_lane=None):
    """선택한 값만 현재 정보에 덮어써서 (새 값 dict, 변경 내역 list, 에러 메시지)를 반환.
    sub_lane == 'none' 이면 부 라인을 삭제"""
    if tier is None and division is None and main_lane is None and sub_lane is None:
        return None, [], "바꿀 항목을 하나 이상 선택해 주세요."

    new_tier = tier or user["tier"]
    if has_division(new_tier):
        new_div = division if division is not None else user["division"]
        if new_div == 0:  # 마스터 이상에서 일반 티어로 바꾸는데 단계를 안 고른 경우
            return None, [], f"{new_tier}는 단계(1~4)도 같이 선택해 주세요."
    else:
        new_div = 0

    new_main = main_lane or user["main_lane"]
    if sub_lane is None:
        new_sub = user["sub_lane"]
    elif sub_lane == "none":
        new_sub = None
    else:
        new_sub = sub_lane

    notes = []
    if new_sub == new_main:
        if sub_lane not in (None, "none"):
            return None, [], "주 라인과 부 라인이 같아요."
        new_sub = None
        notes.append("부 라인이 주 라인과 같아져서 부 라인은 지웠어요.")

    changes = []
    old_label = tier_label(user["tier"], user["division"])
    new_label = tier_label(new_tier, new_div)
    if old_label != new_label:
        changes.append(f"티어: {old_label} → {new_label}")
    if new_main != user["main_lane"]:
        changes.append(f"주 라인: {user['main_lane']} → {new_main}")
    if new_sub != user["sub_lane"]:
        changes.append(f"부 라인: {user['sub_lane'] or '없음'} → {new_sub or '없음'}")
    if not changes:
        return None, [], "바뀐 내용이 없어요. 현재 등록된 값과 같아요."

    values = {"tier": new_tier, "division": new_div, "main_lane": new_main, "sub_lane": new_sub}
    return values, changes + notes, None

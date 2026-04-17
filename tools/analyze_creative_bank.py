"""
Creative Bank 분석 스크립트
E:\Creative bank 폴더의 영상들을 Gemini로 분석해 카피/비주얼 패턴 추출

사용법:
  python analyze_creative_bank.py

결과:
  E:\Creative bank\@분석자료\bank_analysis.json  ← Add Hook 툴에서 import
  E:\Creative bank\@분석자료\processed_files.json ← 재실행 시 건너뛸 파일 목록
"""

import os
import json
import time
import sys
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────────────
CREATIVE_BANK_PATH = Path("E:/Creative bank")
OUTPUT_DIR         = CREATIVE_BANK_PATH / "@분석자료"
OUTPUT_JSON        = OUTPUT_DIR / "bank_analysis.json"
PROGRESS_JSON      = OUTPUT_DIR / "processed_files.json"

# 폴더명 → Add Hook 게임 ID 매핑
GAME_FOLDER_MAP = {
    "PC포커":           "pc_poker",       # PC버전
    "한게임포커 클래식": "pc_poker",       # 모바일버전 — 같은 게임, 같은 ID로 병합
    "우파루 오딧세이":   "uparu_odyssey",
    "한게임 로얄홀덤":  "royal_holdem",
    "한게임 섯다&맞고": "sutda_matgo",
    "한게임 신맞고":    "shin_matgo",
    "한게임 포커":      "hangame_poker",
    "한게임 홀덤":      "holdem",
}

VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".avi", ".gif"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# 무료 티어: 분당 15 요청 → 요청 간 4초 대기
REQUEST_INTERVAL = 4.0
# ─────────────────────────────────────────────────────────────


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("Gemini API 키를 입력하세요 (입력 후 Enter):")
        key = input().strip()
    if not key:
        print("API 키가 없습니다. 종료합니다.")
        sys.exit(1)
    return key


def load_progress():
    if PROGRESS_JSON.exists():
        try:
            return set(json.loads(PROGRESS_JSON.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_progress(processed: set):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROGRESS_JSON.write_text(
        json.dumps(sorted(processed), ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def load_bank():
    if OUTPUT_JSON.exists():
        try:
            return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_bank(bank: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(bank, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def analyze_video(model, file_obj, filename: str) -> list[str]:
    """영상을 Gemini로 분석해 카피·비주얼 패턴 리스트 반환"""
    prompt = f"""이 광고 영상({filename})을 분석해줘.

다음 내용을 추출해서 JSON 배열로만 반환해. 다른 설명 없이 JSON만:
- 화면에 표시된 자막·텍스트 (정확히)
- 성우·나레이션 음성 대사 (정확히)
- 핵심 카피 문구 (있다면)
- 비주얼 연출 특징 1줄 요약 (예: "AI 실사 여성 + 포커칩 + 붉은 고급 배경")

형식: ["카피1", "카피2", "비주얼 설명", ...]
중복 제거, 빈 항목 제외. 최대 10개."""

    try:
        response = model.generate_content(
            [file_obj, prompt],
            generation_config={"max_output_tokens": 512}
        )
        raw = response.text.strip()

        # JSON 배열 파싱
        import re
        m = re.search(r'\[[\s\S]*?\]', raw)
        if m:
            arr = json.loads(m.group())
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception as e:
        print(f"    ⚠️  분석 실패: {e}")
    return []


def analyze_image(model, image_path: Path) -> list[str]:
    """이미지를 Gemini로 분석"""
    import google.generativeai as genai

    prompt = """이 광고 이미지를 분석해줘.
다음 내용을 JSON 배열로만 반환해 (다른 설명 없이):
- 화면에 표시된 텍스트·카피 (정확히)
- 비주얼 연출 특징 1줄 요약

형식: ["카피1", "카피2", "비주얼 설명"]
빈 항목 제외. 최대 8개."""

    try:
        img = genai.upload_file(str(image_path))
        time.sleep(1)
        response = model.generate_content(
            [img, prompt],
            generation_config={"max_output_tokens": 256}
        )
        raw = response.text.strip()

        import re
        m = re.search(r'\[[\s\S]*?\]', raw)
        if m:
            arr = json.loads(m.group())
            entries = [str(x).strip() for x in arr if str(x).strip()]
            # 업로드 파일 삭제
            try: genai.delete_file(img.name)
            except: pass
            return entries
    except Exception as e:
        print(f"    ⚠️  이미지 분석 실패: {e}")
    return []


def wait_for_file(genai, file_obj, timeout=120):
    """Gemini 파일 처리 완료까지 대기"""
    import google.generativeai as genai_module
    start = time.time()
    while True:
        f = genai_module.get_file(file_obj.name)
        if f.state.name == "ACTIVE":
            return f
        if f.state.name == "FAILED":
            raise Exception("파일 처리 실패")
        if time.time() - start > timeout:
            raise Exception("파일 처리 시간 초과")
        time.sleep(3)


def main():
    import google.generativeai as genai

    print("=" * 55)
    print("  Creative Bank 분석 스크립트")
    print("=" * 55)

    api_key = get_api_key()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-001")

    processed = load_progress()
    bank = load_bank()
    print(f"\n이미 처리된 파일: {len(processed)}개")

    # 처리할 파일 목록 수집
    tasks = []
    for folder_name, game_id in GAME_FOLDER_MAP.items():
        folder = CREATIVE_BANK_PATH / folder_name
        if not folder.exists():
            continue
        for f in sorted(folder.rglob("*")):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in VIDEO_EXTENSIONS and ext not in IMAGE_EXTENSIONS:
                continue
            rel = str(f.relative_to(CREATIVE_BANK_PATH))
            if rel in processed:
                continue
            tasks.append((game_id, f, rel, ext in VIDEO_EXTENSIONS))

    total = len(tasks)
    print(f"처리할 파일: {total}개\n")

    if total == 0:
        print("새로 처리할 파일이 없습니다.")
        return

    # 비용 예상
    estimated_cost = total * 0.0012  # 평균 $0.0012/파일
    print(f"예상 비용: ${estimated_cost:.2f} (약 {int(estimated_cost * 1400)}원)")
    print(f"예상 시간: 약 {int(total * REQUEST_INTERVAL / 60)}분 (무료 티어 기준)\n")
    print("시작하려면 Enter, 취소는 Ctrl+C:")
    input()

    errors = 0
    for i, (game_id, file_path, rel_path, is_video) in enumerate(tasks, 1):
        print(f"[{i}/{total}] {file_path.name[:50]}")

        try:
            if is_video:
                print(f"    📤 업로드 중...")
                uploaded = genai.upload_file(str(file_path))
                uploaded = wait_for_file(genai, uploaded)
                print(f"    🔍 분석 중...")
                entries = analyze_video(model, uploaded, file_path.name)
                try: genai.delete_file(uploaded.name)
                except: pass
            else:
                print(f"    🖼️  이미지 분석 중...")
                entries = analyze_image(model, file_path)

            if entries:
                if game_id not in bank:
                    bank[game_id] = []
                # 중복 제거 후 추가
                existing = set(bank[game_id])
                new_entries = [e for e in entries if e not in existing]
                bank[game_id].extend(new_entries)
                print(f"    ✅ {len(new_entries)}개 추출 (누적: {len(bank[game_id])}개)")
            else:
                print(f"    — 추출 없음")

        except KeyboardInterrupt:
            print("\n\n중단됨. 진행 상황 저장 중...")
            break
        except Exception as e:
            print(f"    ❌ 오류: {e}")
            errors += 1
            if errors > 10:
                print("오류가 너무 많습니다. 중단합니다.")
                break

        processed.add(rel_path)

        # 10개마다 중간 저장
        if i % 10 == 0:
            save_bank(bank)
            save_progress(processed)
            print(f"    💾 중간 저장 완료")

        time.sleep(REQUEST_INTERVAL)

    # 최종 저장
    save_bank(bank)
    save_progress(processed)

    print("\n" + "=" * 55)
    print(f"완료! 결과 저장: {OUTPUT_JSON}")
    print("\n게임별 추출 카피 수:")
    for game_id, entries in bank.items():
        print(f"  {game_id}: {len(entries)}개")
    print("\nAdd Hook 툴에서 이 파일을 import하면 카피 뱅크에 반영됩니다.")


if __name__ == "__main__":
    main()

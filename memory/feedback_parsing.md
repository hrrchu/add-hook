---
name: Add Hook 파싱 이슈 및 피드백
description: Add Hook 툴의 AI 응답 파싱 실패 문제와 사용자 피드백
type: feedback
---

Add Hook 툴에서 다각화 생성 시 AI 응답 파싱 실패가 반복 발생.
- 원인: 스트리밍 버퍼 잔여 데이터 미처리 + JSON 래퍼(```json) 제거 실패
- 수정: buffer 잔여분 추가 + indexOf/lastIndexOf 방식 파싱으로 변경
- 상태: 디버그 로그 추가 완료, 추가 확인 필요

**Why:** 사용자가 반복 에러에 불만 ("똑바로 해줄래"). 한 번에 확실히 해결해야 함.
**How to apply:** AI 응답 파싱 관련 변경 시 반드시 테스트 후 배포. 스트리밍 응답 처리 시 buffer 잔여분 처리 필수.

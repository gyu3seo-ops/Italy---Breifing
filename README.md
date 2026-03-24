# 밀라노 주재원 데일리 뉴스 브리핑

매일 아침 자동으로 이탈리아·유럽·글로벌 뉴스를 검색해 인터랙티브 HTML 브리핑을 생성합니다.

---

## 세팅 방법 (딱 10분)

### 1단계 — GitHub 레포 만들기
1. [github.com](https://github.com) 로그인
2. 우상단 `+` → **New repository**
3. Repository name: `italy-briefing`
4. **Public** 선택 (GitHub Pages 무료 사용 위해)
5. **Create repository** 클릭

### 2단계 — 파일 업로드
아래 3개 파일을 레포에 업로드하세요 (Add file → Upload files):
```
briefing.py
requirements.txt
.github/workflows/daily.yml
```

> `.github` 폴더가 안 보이면 GitHub 웹에서 직접 파일 경로를 입력해 생성하세요.
> New file → 파일명에 `.github/workflows/daily.yml` 입력

### 3단계 — API 키 등록
1. [console.anthropic.com](https://console.anthropic.com) → API Keys → **Create Key**
2. 키 복사
3. GitHub 레포 → **Settings** → **Secrets and variables** → **Actions**
4. **New repository secret** 클릭
   - Name: `ANTHROPIC_API_KEY`
   - Secret: 복사한 키 붙여넣기
5. **Add secret**

### 4단계 — GitHub Pages 활성화
1. 레포 → **Settings** → **Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / Folder: `/docs`
4. **Save**

### 5단계 — 첫 실행 테스트
1. 레포 → **Actions** → **Daily News Briefing**
2. **Run workflow** → **Run workflow** 클릭
3. 1~2분 후 완료 → `https://[유저명].github.io/italy-briefing/` 접속!

---

## 이후 사용법

- **자동 실행**: 매일 오전 6시 (밀라노 시간) 자동 업데이트
- **수동 실행**: Actions → Run workflow
- **북마크**: `https://[유저명].github.io/italy-briefing/` 저장해두고 매일 접속

---

## 비용

Claude API 사용량 기준 **하루 약 $0.05~0.15** (한 달 $2~4 수준)

---

## 파일 구조

```
italy-briefing/
├── briefing.py                    # 메인 스크립트
├── requirements.txt               # Python 패키지
├── .github/
│   └── workflows/
│       └── daily.yml             # 자동 실행 설정
└── docs/
    └── index.html                 # 생성된 브리핑 (자동 생성됨)
```

# 도파민 지도 — 배포 가이드

관리자에서 스팟을 하나씩 등록하면 **SQLite DB**(`data/dopamine.db`)에 저장됩니다.

---

## 0. 무료 도메인으로 먼저 시작 (추천)

**별도 도메인 구매 없이** 호스팅이 주는 **무료 서브도메인**으로 바로 시작해도 됩니다.

| 항목 | 내용 |
|------|------|
| 주소 예 | `https://dopamine-map.onrender.com` |
| 비용 | **0원** (Render 무료 플랜) |
| 카카오 지도 | 위 URL을 카카오 콘솔 **사이트 도메인**에 등록하면 OK |
| 나중에 | 유료 도메인(`dopaminemap.kr` 등) 사도 Render에서 **Custom Domain**으로 연결 가능 |

### 무료로 먼저 할 때 주의 (DB)

Render **무료** 플랜은 디스크가 없어서, **재배포·장기 슬립 후 SQLite가 초기화**될 수 있습니다.  
「일단 올려보고 관리자에서 하나씩 등록해 보기」→ **무료 OK**  
「등록한 스팟을 계속 유지」→ 나중에 `render.yaml`(Starter + 디스크)로 바꾸거나 PythonAnywhere 등 사용

### 무료 배포 방법

GitHub에 ZIP 올린 뒤 Render **New → Blueprint**에서  
저장소의 **`render-free.yaml`** 내용을 `render.yaml`로 이름 바꿔 쓰거나,  
Blueprint 생성 시 `render-free.yaml` 파일을 `render.yaml`로 복사해 커밋한 저장소를 연결하세요.

---

## 1. 배포 전 체크 (5분)

### 카카오 개발자 콘솔

배포 URL을 등록해야 지도·주소 검색이 동작합니다.

1. [developers.kakao.com](https://developers.kakao.com/console/app) → **도파민지도** 앱
2. **플랫폼** → Web → 사이트 도메인에 배포 주소 추가  
   예: `https://dopamine-map.onrender.com`
3. **JavaScript 키** → `index.html`의 `KAKAO_JS_KEY`와 일치하는지 확인
4. **REST API 키** → `admin.html`의 `KAKAO_REST_API_KEY`와 일치하는지 확인

### 관리자 비밀번호

호스팅 환경변수 **`ADMIN_PASSWORD`** 를 설정하세요 (기본 `1111` 말고 강한 비밀번호 권장).  
관리자 로그인·API 등록 모두 이 값과 **동일**해야 합니다.

---

## 2. Render로 배포 (약 10분)

> **처음엔 무료**: `render-free.yaml` 사용 → `*.onrender.com`  
> **스팟 영구 보관**: `render.yaml` (Starter + 디스크, 월 약 $7)

> Git CLI 없어도 됩니다. GitHub 웹에서 ZIP 업로드 가능.

### 2-1. GitHub에 올리기

1. [github.com/new](https://github.com/new) → 저장소 생성 (예: `dopamine-map`, Public)
2. **Add file → Upload files**
3. `pack-deploy.bat` 실행 후 나온 `dopamine-map-deploy.zip` 업로드  
   (또는 폴더 전체를 드래그 — `.env`는 올리지 마세요)

### 2-2. Render 연결

1. [render.com](https://render.com) 가입
2. **New → Blueprint**
3. GitHub 저장소 연결 → `render.yaml` 자동 인식
4. **Environment**에서 `ADMIN_PASSWORD` 입력 (Render가 물어봄)
5. **Deploy**

배포 완료 후 URL 예:

- 사용자: `https://YOUR-APP.onrender.com/`
- 관리자: `https://YOUR-APP.onrender.com/admin.html`

### 2-3. DB 유지 (중요)

`render.yaml`은 **Starter 플랜 + 1GB 디스크**(`/app/data`)를 사용합니다.  
무료 플랜만 쓰면 재배포 시 SQLite가 초기화될 수 있습니다.

---

## 3. 배포 후 사용법

1. `https://YOUR-APP.onrender.com/admin.html` 접속
2. `ADMIN_PASSWORD`로 로그인
3. 스팟 등록 → DB 저장 → 사용자 화면에 즉시 반영
4. `/admin.html` URL은 외부에 공유하지 마세요

헬스 체크: `https://YOUR-APP.onrender.com/api/health` → `{"ok":true}`

---

## 4. 로컬에서 테스트

```powershell
cd C:\Users\user\Desktop\dopamine-map
run.bat
```

- http://127.0.0.1:8080/
- http://127.0.0.1:8080/admin.html

---

## 5. Docker (VPS 등)

```bash
docker build -t dopamine-map .
docker run -p 8080:8080 -e ADMIN_PASSWORD=your-secret -v dopamine-data:/app/data dopamine-map
```

---

## 6. 문제 해결

| 증상 | 해결 |
|------|------|
| 지도 안 뜸 | 카카오 콘솔에 배포 도메인 등록 |
| 등록 시 401 | `ADMIN_PASSWORD`와 관리자 로그인 비밀번호 일치 확인 |
| 재배포 후 스팟 사라짐 | Render 디스크(Starter) 또는 Docker volume 사용 |
| Render 첫 접속 느림 | 무료/슬립 후 깨우는 데 30초~1분 걸릴 수 있음 |

---

## 파일 구조

```
dopamine-map/
├── index.html          # 사용자 앱
├── admin.html          # 관리자 (스팟 CRUD)
├── js/spots-store.js   # API 클라이언트
├── server/             # FastAPI + SQLite
├── data/               # DB (배포 시 볼륨에 마운트)
├── Dockerfile
├── render.yaml
└── .env.example        # ADMIN_PASSWORD 참고
```

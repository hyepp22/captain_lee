# 꺼삐딴 리: 문학 탐험 기록관

전광용의 「꺼삐딴 리」를 읽은 학생을 위한 태블릿 웹게임입니다. 지도와
사물은 학습을 위한 가상 구성입니다. 실제 소설의 장면이나 사물이라고
단정하지 마세요. 교사는 읽기 자료를 확인한 뒤 문항과 근거를 직접 입력합니다.

## 준비물

- Python 3.11 이상
- Node.js 20 이상 및 npm
- GitHub 저장소
- Google Cloud 프로젝트와 편집 가능한 Google 스프레드시트
- Streamlit Community Cloud 계정

## 설치 및 실행

1. 이 프로젝트를 GitHub 저장소에 넣고 로컬에 복제합니다.
2. 가상 환경을 만든 뒤 `pip install -r requirements.txt`를 실행합니다.
3. `cd game_component/frontend`에서 `npm install`을 실행합니다.
4. 같은 폴더에서 `npm run build`를 실행합니다.
5. 생성된 `package-lock.json`과 `build/`를 GitHub에 함께 반영합니다.
6. 프로젝트 루트로 돌아와 Secrets를 설정한 뒤
   `streamlit run app.py`를 실행합니다.

`npm run build` 없이 앱을 시작하면 게임 컴포넌트가 실행되지 않습니다.

## Google Cloud 및 스프레드시트 연결

1. Google Cloud 프로젝트에서 **Google Sheets API**를 활성화합니다.
2. 서비스 계정을 만들고 JSON 키를 발급합니다.
3. 게임용 스프레드시트를 만들고 서비스 계정의 `client_email`에
   **편집자 권한**을 부여합니다.
4. 스프레드시트 주소의 ID를 복사합니다.
5. `.streamlit/secrets.example.toml`을 참고해
   `.streamlit/secrets.toml`을 만듭니다. 이 실제 파일은 GitHub에
   올리지 않습니다.
6. JSON 키의 `private_key`는 줄바꿈이 유지되도록 Streamlit Secrets에
   정확히 입력합니다.
7. `teacher_access_code`는 `CHANGE_ME`가 아닌 값으로 바꿉니다.
   `class_access_code`를 비우면 학급 코드 입력을 요구하지 않습니다.

## 시트 템플릿

각 탭의 **첫 행**에 아래 쉼표로 구분된 이름을 순서대로 한 칸씩 입력합니다.
열 이름은 대소문자까지 코드와 일치해야 합니다. 앱은 기존 자료를
자동으로 초기화하거나 삭제하지 않습니다.

### Questions

`question_id,is_active,quest_id,object_id,question_order,question_type,question_text,option_a,option_b,option_c,option_d,correct_answer,grading_mode,points,max_attempts,hint,explanation,learning_goal,source_note`

### Quests

`quest_id,is_active,quest_order,title,description,map_id,prerequisite_quest_id,reward_clue,completion_message`

### Objects

`object_id,is_active,map_id,object_name,object_type,x,y,interaction_text,quest_id,question_id,appearance_note`

### Responses

`response_id,session_id,submitted_at,grade,class,number,student_name,quest_id,question_id,question_type,answer,attempt_no,is_correct,earned_points,grading_status,elapsed_seconds`

### GameResults

`session_id,started_at,ended_at,grade,class,number,student_name,total_score,total_possible,correct_answers,objective_answers,accuracy,completed_quests,collected_clues,completion_status,reflection`

### Settings — 선택 사항

`key,value`

`reflection_1`, `reflection_2`, `reflection_3`의 `value`를 수정하면 새
게임 세션의 성찰 질문을 바꿀 수 있습니다. Settings 탭이 없으면 앱의
기본 성찰 질문 세 개를 사용합니다.

## 문항 연결과 입력 규칙

- 활성 행의 `is_active`에는 `TRUE`, 비활성 행에는 `FALSE`를 씁니다.
- 먼저 Quests에 퀘스트를 만들고, Objects의 `quest_id`로 연결합니다.
- Questions에는 해당 `quest_id`와 `object_id`를 입력합니다.
- 모든 활성 퀘스트와 사물에는 적어도 한 개의 활성 문항이 필요합니다.
- 사물 하나에 문항 여러 개를 연결할 수 있습니다. 그 경우
  `question_order` 순서대로 풉니다. Objects의 `question_id`는 해당
  사물에 연결된 문항 ID 하나를 넣거나 비워 둘 수 있습니다.
- 같은 지도에서는 `map_id`로 `hall`을 사용할 수 있습니다.
- 사물 좌표는 폭 960, 높이 600 기준이며 x는 32~928, y는 32~568입니다.
  기본 벽과 겹치지 않는 위치를 선택하세요. 화면 크기가 바뀌어도
  이 기준 좌표는 유지됩니다.
- 객관식 `question_type`은 `single_choice` 또는
  `multiple_choice`, `grading_mode`는 `auto`입니다.
- 단일 선택 정답은 `A`, 복수 선택 정답은 `A,C`처럼 쉼표로 구분합니다.
- 서술형은 `question_type=short_answer`, 기본
  `grading_mode=teacher_review`를 권장합니다. 의미 해석을 요구하는
  문항을 기계적으로 오답 처리하지 않습니다.
- **폐쇄형 단답**만 `grading_mode=auto`,
  `correct_answer=exact:표현1|표현2` 형식으로 설정할 수 있습니다.
  나열된 표현과 일치하면 정답, 일치하지 않으면 오답이 아니라
  **교사 검토 필요** 상태가 됩니다.
- 선택형 문항의 `max_attempts`는 기본값으로 `2`를 입력하세요.
  허용 범위는 1~5입니다. 서술형 교사 검토 문항은 `1`을 권장합니다.
- `points`는 0~1000의 정수입니다.
- `source_note`에는 교사가 확인한 본문 또는 학습 자료 근거를 기록합니다.
  작품의 사건·인용문을 확인 없이 만들어 입력하지 마세요.

예를 들어 퀘스트 ID `person`, 사물 ID `person_record`, 문항 ID
`person_01`을 서로 연결할 수 있습니다. **실제 문항 본문과 정답은
수업에서 사용하는 작품 본문을 확인한 교사가 입력해야 합니다.**

퀘스트를 네 개 구성할 경우 `quest_order` 1~4가 지도 화면의 구역
표시에 순서대로 사용됩니다. 선행 조건은
`prerequisite_quest_id`에 앞 퀘스트 ID를 적습니다. 비워 두면
바로 시작할 수 있습니다.

## 한글 PDF

인쇄용 HTML 보고서는 추가 글꼴 없이 제공됩니다. 한글 PDF를
사용하려면 배포 가능한 라이선스를 직접 확인한
`NotoSansKR-Regular.ttf`를 `assets/NotoSansKR-Regular.ttf`에 넣고
라이선스 고지 의무를 지킨 뒤 배포하세요. 글꼴이 없으면 앱은
깨진 PDF를 만들지 않고 인쇄용 HTML을 제공합니다.

## 배포

1. 실제 Secrets 파일과 서비스 계정 JSON이 GitHub에 없는지 확인합니다.
2. `package-lock.json` 및 `game_component/frontend/build/`을 포함해
   소스를 GitHub에 반영합니다.
3. Streamlit Community Cloud에서 저장소의 `app.py`를 진입점으로
   선택합니다.
4. 배포 설정의 **Secrets**에 실제 TOML 설정을 입력합니다.
5. 배포 후 태블릿 브라우저에서 방향 패드, 답안 제출, 저장 상태,
   성찰 및 보고서 다운로드를 직접 확인합니다.
6. 교사는 Sheets의 Questions·Quests·Objects를 수정한 뒤 교사용
   화면에서 **문항 데이터 새로고침**을 누릅니다. 진행 중인 학생
   세션의 채점 기준은 유지되고 새 세션에 수정 내용이 적용됩니다.
7. 교사용 화면과 스프레드시트의 Responses·GameResults에서 기록을
   확인합니다.

## 운영 및 보안상 한계

- 교사 접근 코드는 간편한 화면 제한이며 완전한 신원 인증이 아닙니다.
  민감한 학생 정보를 다룬다면 별도 인증·접근 통제 정책이 필요합니다.
- 저장에 실패한 응답은 **현재 Streamlit 서버 세션에만** 남습니다.
  저장을 확인하기 전 브라우저 탭을 닫거나 서버가 재시작되면
  복구할 수 없습니다.
- 동일한 저장 ID에 대해 재조회하고 한 서버 프로세스 내 쓰기를
  직렬화합니다. 그러나 Google Sheets에는 고유 키 제약이나
  원자적 조건부 추가 기능이 없으므로 **서로 다른 서버 프로세스가
  동시에 같은 ID를 추가하는 극단적 상황의 정확히 한 번 저장까지
  보장하지는 않습니다**. 엄격한 거래 보장이 필요하면 별도
  트랜잭션 저장소가 필요합니다.
- Google Sheets 할당량과 학생 수를 고려해 수업 전에 실제 동시
  접속 시험을 하세요. 교사 조회는 버튼을 눌렀을 때 실행됩니다.
- 완결된 답안의 정답은 서버가 허용한 시점에만 피드백에 포함됩니다.
  전체 정답표와 Google 인증 정보는 게임 컴포넌트로 보내지 않습니다.

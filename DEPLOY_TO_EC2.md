# AWS EC2 배포 가이드

이 가이드는 Flask 애플리케이션을 AWS EC2 인스턴스(Ubuntu 기준)에 배포하고 상시 구동하는 방법을 단계별로 설명합니다.

## 1. AWS EC2 인스턴스 생성
1. **AWS 콘솔 접속**: AWS에 로그인 후 'EC2' 서비스를 검색하여 이동합니다.
2. **인스턴스 시작**: '인스턴스 시작' 버튼을 클릭합니다.
3. **이름 및 태그**: 인스턴스 이름을 입력합니다 (예: `MyFlaskServer`).
4. **AMI 선택**: 'Ubuntu'를 선택합니다 (Ubuntu Server 22.04 LTS 또는 24.04 LTS 추천 - 프리 티어 사용 가능).
5. **인스턴스 유형**: 't2.micro' (프리 티어 사용 가능)를 선택합니다.
6. **키 페어**: '새 키 페어 생성'을 클릭하여 `.pem` (Mac/Linux) 또는 `.ppk` (Windows PuTTY용) 파일을 다운로드하고 잘 보관합니다.
7. **네트워크 설정**:
    - '인터넷에서 HTTP 트래픽 허용', '인터넷에서 HTTPS 트래픽 허용'을 체크합니다.
    - SSH (포트 22)는 기본적으로 내 IP에서만 허용하는 것이 안전하지만, 편의상 '위치 무관'으로 설정할 수도 있습니다.
8. **스토리지**: 기본값(8GB 또는 30GB) 그대로 둡니다.
9. **시작**: '인스턴스 시작'을 클릭하여 서버를 생성합니다.

## 2. EC2 인스턴스 접속
### Windows (PuTTY 사용)
1. 인스턴스 목록에서 생성한 인스턴스의 '퍼블릭 IPv4 주소'를 복사합니다.
2. PuTTY를 실행합니다.
3. **Host Name**: `ubuntu@<퍼블릭 IP 주소>` 입력 (예: `ubuntu@3.123.45.67`)
4. **SSH > Auth > Credentials**: 다운로드 받은 `.ppk` private key 파일을 불러옵니다.
5. 'Open'을 클릭하여 접속합니다.

### Mac/Linux (Terminal 사용)
1. 터미널을 엽니다.
2. 키 파일 권한 설정: `chmod 400 my-key.pem`
3. 접속: `ssh -i my-key.pem ubuntu@<퍼블릭 IP 주소>`

## 3. 서버 환경 설정
접속한 터미널에서 다음 명령어들을 순서대로 입력하여 필요한 프로그램을 설치합니다.

```bash
# 패키지 목록 업데이트
sudo apt update

# Python, Pip, Git 설치
sudo apt install python3-pip python3-venv git -y

# 프로젝트 폴더 생성 및 이동 (선택 사항)
mkdir myapp
cd myapp
```

## 4. 프로젝트 코드 가져오기
GitHub와 같은 저장소를 사용한다면 `git clone`을, 아니라면 파일 전송 툴(FileZilla 등)을 이용해 코드를 올립니다. 여기서는 가상의 시나리오로 설명합니다.

```bash
# Git을 사용하는 경우 (추천)
git clone https://github.com/wanwoo-choi/EM-main
cd <프로젝트_폴더명>
```

> **팁**: Git을 안 쓴다면, 로컬에서 `scp`나 FileZilla로 `app.py`, `requirements.txt`, `Procfile`, `templates/`, `*.json` 파일들을 서버의 `/home/ubuntu/myapp` 경로로 업로드하세요.

## 5. 의존성 설치 및 가상환경 설정
```bash
# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt
```

## 6. AWS RDS (데이터베이스) 생성 및 윈도우에서 연결
RDS를 생성하고, **내 컴퓨터(윈도우)에서 편하게 접속**해서 테이블을 세팅하는 방법입니다.

### 6-1. RDS 데이터베이스 생성 (중요 설정 포함)
1. **AWS 콘솔** -> `RDS` -> **'데이터베이스 생성'**.
2. **Standard Create (표준 생성)** -> `MySQL`.
3. **템플릿**: **'Free Tier (프리 티어)'** 선택.
4. **설정**: `echomind-db`, `admin`, `mypassword1234` (비번 기억!).
5. **연결 (Connectivity)**:
    - **컴퓨팅 리소스 연결**: `연결 안 함` 선택.
    - **퍼블릭 액세스 (Public access)**: **'예 (Yes)'** 선택 (매우 중요! 이거 안 하면 집에서 접속 못 함).
    - **VPC 보안 그룹**: '새로 생성' (이름: `rds-sec-group` 등).
6. **추가 구성**: '초기 데이터베이스 이름'에 `echomind` 입력.
7. **생성** 클릭.

### 6-2. RDS 보안 그룹 설정 (내 컴퓨터 허용)
RDS가 생성되는 동안 보안 그룹을 열어줍니다.
1. RDS 목록에서 해당 DB 클릭 -> '연결 및 보안' -> **보안 그룹 링크** 클릭.
2. **'인바운드 규칙 편집'** -> **규칙 추가**.
3. **유형**: `MYSQL/Aurora` (3306).
4. **소스**: **'내 IP (My IP)'** 선택 (현재 집 IP 자동 입력됨).
    - *참고: 나중에 EC2에서 접속하려면 EC2의 보안 그룹 ID도 여기에 추가해줘야 합니다!*
5. **저장**.

### 6-3. 윈도우에서 테이블 생성하기 (`init_db.py` 실행)
프로젝트 폴더에 제가 만들어드린 `init_db.py` 파일이 있습니다. 이걸 윈도우에서 바로 실행해서 RDS에 테이블을 만듭니다.

1. VS Code에서 `init_db.py` 파일을 엽니다.
2. `RDS_HOST = "..."` 부분에 **RDS 엔드포인트**를 복사해서 붙여넣습니다. (RDS 상태가 '사용 가능'일 때 보임)
3. 터미널에서 실행:
   ```bash
   python init_db.py
   ```
   *(`pymysql`이 없다면 `pip install pymysql` 먼저 실행)*
4. "모든 테이블 생성 완료!" 메시지가 뜨면 성공입니다.

### 6-4. EC2 서버에서 코드 수정
이제 EC2에 접속해서(새로 만들었으니 `git clone` 다시 하시고), `app.py`의 DB 정보만 바꿔주면 됩니다.

```bash
# EC2 접속 후
git clone https://github.com/wanwoo-choi/EM-main
cd EM-main
nano app.py
```
`db_config`의 `host`뿐만 아니라, `user`, `password`도 **RDS 생성 시 설정한 값**으로 바꿔야 합니다.

```python
# nano 에디터에서 아래와 같이 수정하세요 (화살표 키로 이동)
db_config = {
    'host': '복사한_RDS_엔드포인트_주소',  # 예: echomind-db.xxxx.rn.rds.amazonaws.com
    'user': 'admin',                      # RDS 마스터 사용자 이름
    'password': 'mypassword1234',         # RDS 비밀번호 (8자 이상 필수!)
    'db': 'echomind',                     # 초기 데이터베이스 이름
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
```
수정 후 저장하려면 `Ctrl + O` 누르고 `Enter`, 나가려면 `Ctrl + X`를 누르세요.

## 7. 애플리케이션 실행
설정이 끝났으니 서버를 가동합니다.

```bash
# 백그라운드 실행
nohup gunicorn -b 0.0.0.0:5000 app:app &
```

## 8. AWS 보안 그룹 설정 (포트 열기)
1. AWS EC2 콘솔 -> '보안(Security)' 탭 -> '보안 그룹(Security groups)' 클릭.
2. '인바운드 규칙 편집(Edit inbound rules)' 클릭.
3. '규칙 추가' -> 유형: `사용자 지정 TCP`, 포트: `5000`, 소스: `Anywhere-IPv4 (0.0.0.0/0)`.
4. '규칙 저장'.
5. 다시 브라우저에서 `http://<퍼블릭 IP>:5000` 접속 확인.

## 8. 상시 구동 (백그라운드 실행)
터미널을 꺼도 서버가 계속 돌아가게 하려면 `nohup`을 사용합니다.

```bash
# 백그라운드 실행 (로그는 nohup.out에 저장됨)
nohup gunicorn -b 0.0.0.0:5000 app:app &
```

이제 터미널을 종료해도 서버는 계속 실행됩니다.

### 서버 중지 방법
```bash
# 실행 중인 프로세스 확인
ps aux | grep gunicorn

# 강제 종료 (PID는 위 명령어로 확인한 번호)
kill -9 <PID>
# 또는 모든 gunicorn 프로세스 종료
pkill gunicorn
```

---
**축하합니다! 이제 당신의 서비스가 AWS EC2 위에 배포되었습니다.**
메모: 테스트 서버 열면서 발생한 오류들이 몇가지 있음
1. 처음에 키 만들면 잘 보관해야함. 없으면 ㅈ댐. 
2. 리전을 처음부터 서울에 제대로 해야함. 옮기려면 삭제 후 인스턴스 재생성해야함
3. 깃허브 퍼블릭으로 해야되며 프라이빗이면 아이디비번쳐야함
4. 요구 라이브러리에 한글 주석이라도 들어가면 안된다 아니면 오류남
5. 인바운드 보안 그룹에서 TCP5000번 포트 열어줘야함 전체공개하면 위험할수있다고함

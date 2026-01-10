# 🧠 EchoMind : AI 기반 성격 분석 소셜 매칭 시스템

### 📖 프로젝트 개요

본 프로젝트의 목적은 AI가 사용자의 실제 대화 데이터를 분석하여 성격을 자동 분석하고, 그 결과를 기반으로 성향이 잘 맞는 친구를 추천하는 시스템을 개발하는 것입니다. <br>
설문 없이 자연스러운 언어 표현만으로 성격을 파악한다는 점에서 기존 성격검사와 차별화되며, 이를 통해 대화 속 언어 패턴이 사람의 성향을 얼마나 정확히 반영할 수 있는지 실험적으로 검증하고자 합니다. <br>
또한 인공지능과 자연어처리 기술을 활용하여, 사용자와 잘 맞는 사람을 찾아주는 새로운 방식의 성격 분석 플랫폼을 제시합니다.

## 📁 시스템 구조도

![system](https://github.com/user-attachments/assets/95e83d65-fe4a-4a84-a885-d02b1c9967e9)

<br>

## 🛠️ 기술 스택

### 개발 언어 및 프레임워크
<table>
  <tr>
    <td align="center">
      <img src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg" alt="Python" width="50" height="50"/>
      <br>Python 3.9+
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/flask/000000" alt="Flask" width="50" height="50"/>
      <br>Flask
    </td>
  </tr>
</table>

### AI 및 데이터베이스
<table>
  <tr>
    <td align="center">
      <img src="https://upload.wikimedia.org/wikipedia/commons/4/4d/OpenAI_Logo.svg" alt="OpenAI" width="50" height="50"/>
      <br>OpenAI API
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/mysql/4479A1" alt="MySQL" width="50" height="50"/>
      <br>MySQL
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/sqlite/003B57" alt="SQLite" width="50" height="50"/>
      <br>SQLite
    </td>
  </tr>
</table>

### 서버 및 인프라
<table>
  <tr>
    <td align="center">
      <img src="https://cdn.simpleicons.org/amazonaws/FF9900?v=new" alt="AWS" width="50" height="50"/>
      <br>AWS
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/ubuntu/E95420" alt="Ubuntu" width="50" height="50"/>
      <br>Ubuntu
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/nginx/009639" alt="Nginx" width="50" height="50"/>
      <br>Nginx
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/gunicorn/499848" alt="Gunicorn" width="50" height="50"/>
      <br>Gunicorn
    </td>
  </tr>
</table>

### 개발 및 협업 도구
<table>
  <tr>
    <td align="center">
      <img src="https://upload.wikimedia.org/wikipedia/commons/1/1d/PyCharm_Icon.svg" alt="PyCharm" width="50" height="50"/>
      <br>PyCharm
    </td>
    <td align="center">
      <img src="https://upload.wikimedia.org/wikipedia/commons/9/9a/Visual_Studio_Code_1.35_icon.svg" alt="VS Code" width="50" height="50"/>
      <br>VS Code
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/git/F05032" alt="Git" width="50" height="50"/>
      <br>Git
    </td>
    <td align="center">
      <img src="https://cdn.simpleicons.org/github/181717" alt="GitHub" width="50" height="50"/>
      <br>GitHub
    </td>
    <td align="center">
      <img src="https://upload.wikimedia.org/wikipedia/commons/4/45/Notion_app_logo.png" alt="Notion" width="50" height="50"/>
      <br>Notion
    </td>
  </tr>
</table>

<br>

## 💻 개발 환경

#### 로컬 개발 환경
| 구분 | 환경 |
| :---: | :---: |
| **운영체제** | Windows 10 / 11 |
| **개발 도구** | Visual Studio Code, PyCharm |
| **언어** | Python 3.9+ (Virtualenv 권장) |
| **데이터베이스** | Local MySQL / SQLite |
| **버전 관리** | Git & GitHub |

<br>

## 🚀 운용 환경

#### AWS 클라우드 환경
| 구분 | 환경 |
| :---: | :---: |
| **클라우드 플랫폼** | Amazon Web Services (AWS) |
| **서버 (Compute)** | AWS EC2 (t2.micro / t3.small) |
| **서버 운영체제** | Ubuntu Linux 24.04 LTS |
| **데이터베이스** | Amazon RDS (MySQL) |
| **웹 서버** | Nginx (Reverse Proxy) |
| **WSGI 서버** | Gunicorn |
| **AI 모델** | OpenAI GPT-5.1 mini (API) |

**※ 배포:** GitHub Actions를 통한 CI/CD 파이프라인 구축 (예정)

---

## 3. 프로젝트 로드맵

<img width="1408" height="752" alt="roadmap" src="https://github.com/user-attachments/assets/f95fe632-3fff-4a77-9f27-25f7e3c40784" />



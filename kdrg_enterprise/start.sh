#!/bin/bash

# KDRG Enterprise 시작 스크립트

echo "==================================="
echo "  KDRG Enterprise 시스템 시작"
echo "==================================="

# 디렉토리 확인
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Backend 시작
echo ""
echo "[1/2] Backend 서버 시작 중..."
cd backend

INSTALL_DEPS=0
# Python 가상환경 생성 (없으면)
if [ ! -d "venv" ]; then
    echo "  가상환경 생성 중..."
    python3 -m venv venv
    INSTALL_DEPS=1
fi

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치 (최초 생성 또는 강제 설치 시)
if [ "${FORCE_PIP_INSTALL:-0}" = "1" ] || [ ${INSTALL_DEPS} -eq 1 ] || [ ! -f "venv/.deps-installed" ]; then
    echo "  패키지 설치 중..."
    pip install -r requirements.txt -q
    touch venv/.deps-installed
else
    echo "  패키지 설치 건너뜀 (venv/.deps-installed 존재)"
fi

# 디렉토리 생성
mkdir -p data logs data/uploads data/exports

# Backend 서버 시작 (백그라운드)
APP_PORT=${APP_PORT:-8081}

echo "  FastAPI 서버 시작 (포트: ${APP_PORT})..."
uvicorn main:app --host 0.0.0.0 --port "${APP_PORT}" --reload &
BACKEND_PID=$!

cd ..

# Frontend 시작
echo ""
echo "[2/2] Frontend 서버 시작 중..."
cd frontend

# Node.js 패키지 설치
if [ "${FORCE_NPM_INSTALL:-0}" = "1" ] || [ ! -d "node_modules" ]; then
    echo "  npm 패키지 설치 중..."
    npm install
else
    echo "  npm 패키지 설치 건너뜀 (node_modules 존재)"
fi

# Frontend 서버 시작
FRONTEND_PORT=${FRONTEND_PORT:-3001}

echo "  Vite 개발 서버 시작 (포트: ${FRONTEND_PORT})..."
PORT=${FRONTEND_PORT} npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "==================================="
echo "  KDRG Enterprise 시작 완료!"
echo "==================================="
echo ""
echo "  Backend:  http://localhost:${APP_PORT}"
echo "  Frontend: http://localhost:${FRONTEND_PORT}"
echo "  API Docs: http://localhost:${APP_PORT}/api/docs"
echo ""
echo "  테스트 계정: admin / admin123"
echo ""
echo "  종료하려면 Ctrl+C를 누르세요."
echo ""

# 프로세스 종료 핸들러
cleanup() {
    echo ""
    echo "서버 종료 중..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# 대기
wait

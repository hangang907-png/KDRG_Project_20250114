
import asyncio
import httpx
import xml.etree.ElementTree as ET

async def test_v2_api():
    api_key = "3bdd9d35b0a44e615fe80ca653d7265b3ce463b24485a368d3d6748ad7bbb224"
    
    # 테스트할 URL 목록 (v1, v2, http, https 조합)
    urls = [
        "http://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList",
        "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList",
        "http://apis.data.go.kr/B551182/hospInfoService/getHospBasisList" # v1
    ]
    
    params = {
        "serviceKey": api_key,
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    print(f"Testing with key: {api_key[:10]}...")
    
    async with httpx.AsyncClient(verify=False) as client: # SSL 인증서 무시
        for url in urls:
            print(f"\n--- Testing URL: {url} ---")
            try:
                response = await client.get(url, params=params, timeout=10.0)
                print(f"Status Code: {response.status_code}")
                content = response.text[:500] # 앞부분만 출력
                print(f"Content: {content}")
                
                if "<resultCode>00</resultCode>" in content:
                    print(">>> SUCCESS! 이 URL이 정답입니다.")
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_v2_api())

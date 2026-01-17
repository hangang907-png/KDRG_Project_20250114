
import asyncio
import httpx

async def test_api():
    api_key = "3bdd9d35b0a44e615fe80ca653d7265b3ce463b24485a368d3d6748ad7bbb224"
    url = "http://apis.data.go.kr/B551182/hospInfoService/getHospBasisList"
    params = {
        "serviceKey": api_key,
        "numOfRows": "1",
        "pageNo": "1"
    }
    
    print(f"Testing API with key: {api_key[:10]}...")
    async with httpx.AsyncClient() as client:
        try:
            # 1. 시도 (이미 인코딩된 키일 수 있으므로 그대로 보냄)
            response = await client.get(url, params=params)
            print(f"\n[Response Content]\n{response.text}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())


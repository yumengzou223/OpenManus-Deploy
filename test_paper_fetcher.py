import asyncio
import traceback
import os
from app.tool.paper_fetcher import PaperFetcherTool

async def test():
    print("Starting test", flush=True)
    print("CWD:", os.getcwd(), flush=True)
    tool = PaperFetcherTool()
    try:
        result = await tool.execute(
            keyword='RAG retrieval augmented generation',
            max_results=5,
            sort_by='lastUpdatedDate'
        )
        print("Got result", flush=True)
        output_text = str(result)
        print("Converted to string", flush=True)
        with open('F:\\openmanus\\OpenManus\\test_output.txt', 'w', encoding='utf-8') as f:
            f.write(f"Type: {type(result)}\n")
            f.write(f"Result str: {output_text}\n")
        print("Done writing", flush=True)
    except Exception as e:
        print(f"Exception: {e}", flush=True)
        with open('F:\\openmanus\\OpenManus\\test_output.txt', 'w', encoding='utf-8') as f:
            f.write(f"Exception: {e}\n")
            f.write(traceback.format_exc())

asyncio.run(test())

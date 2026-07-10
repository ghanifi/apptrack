FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

COPY apptrack_mcp/ ./apptrack_mcp/

ENV MCP_TRANSPORT=streamable-http
ENV MCP_PORT=8010

EXPOSE 8010

CMD ["python", "-m", "apptrack_mcp.server"]

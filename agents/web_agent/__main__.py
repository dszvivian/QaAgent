import uvicorn
import asyncio

from a2a.types import AgentSkill, AgentCard, AgentCapabilities
import asyncclick as click
from a2a.server.request_handlers import DefaultRequestHandler

from agents.web_agent.agent_executor import  WebAgentAgentExecutor
from a2a.server.tasks import InMemoryTaskStore
from a2a.server.apps import A2AStarletteApplication

@click.command()
@click.option('--host', default='localhost', help='Host for the agent server')
@click.option('--port', default=10002, help='Port for the agent server')
async def main(host: str, port: int):
    """
    Main function to automate Web realted tasks.
    """
    skill = AgentSkill(
        id="web_agent_skill",
        name="web_agent_skill",
        description="A web agent to automate tasks",
        tags=["playwright", "webagent", ],
        examples=[
            """go to google.com and search for iphone""",
            """goto dev.dynamics.com and create a Sales Order""",
        ]
    )

    agent_card = AgentCard(
        name ="web_agent",
        description="A Web Agent that can automate tasks given to it",
        url=f"http://{host}:{port}/",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[skill],
        capabilities=AgentCapabilities(streaming=True),
    )
    
    agent_executor = WebAgentAgentExecutor()
    await agent_executor.create()

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=InMemoryTaskStore()
    )

    server = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )

    config = uvicorn.Config(server.build(), host=host, port=port)
    server_instance = uvicorn.Server(config)
    
    await server_instance.serve()


if __name__ == "__main__":
    asyncio.run(main())
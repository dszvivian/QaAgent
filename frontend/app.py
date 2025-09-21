import logging
import subprocess

import os
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import bleach
import httpx
import socketio
import validators

from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    AgentCard,
    JSONRPCErrorResponse,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    Role,
    SendMessageRequest,
    SendMessageResponse,
    SendStreamingMessageRequest,
    SendStreamingMessageResponse,
    TextPart,
    Task,
    TaskStatus,
    TaskStatusUpdateEvent
)
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


STANDARD_HEADERS = {
    'host',
    'user-agent',
    'accept',
    'content-type',
    'content-length',
    'connection',
    'accept-encoding',
}

# ==============================================================================
# Setup
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI()
# NOTE: In a production environment, cors_allowed_origins should be restricted
# to the specific frontend domain, not a wildcard '*'.
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
socket_app = socketio.ASGIApp(sio)
app.mount('/socket.io', socket_app)

# Current directory where app.py is located
current_dir = os.path.dirname(os.path.abspath(__file__))

# Mount templates directory
templates = Jinja2Templates(directory=current_dir)

# Mount static files directory - important for CSS and JS to load properly
static_dir = os.path.join(current_dir, "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
else:
    logger.warning(f"Static directory not found at {static_dir}. Creating directory.")
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ==============================================================================
# State Management
# ==============================================================================

# NOTE: This global dictionary stores state. For a simple inspector tool with
# transient connections, this is acceptable. For a scalable production service,
# a more robust state management solution (e.g., Redis) would be required.
clients: dict[str, tuple[httpx.AsyncClient, A2AClient, AgentCard]] = {}

# Store active chat sessions with their option types
chat_sessions: dict[str, str] = {}  # {sid: option_type}

# Flag to track if welcome message has been sent
welcome_sent: dict[str, bool] = {}

# ==============================================================================
# Socket.IO Event Helpers
# ==============================================================================

def extract_content(
    message_parts,
) -> list[tuple[str | dict[str, Any], str]]:
    message = ""
    for part in message_parts:
        p = part.root
        if p.kind == 'text':
            message += p.text
    return message


async def _emit_debug_log(
    sid: str, event_id: str, log_type: str, data: Any
) -> None:
    """Helper to emit a structured debug log event to the client."""
    await sio.emit(
        'debug_log', {'type': log_type, 'data': data, 'id': event_id}, to=sid
    )


async def _process_a2a_response(
    result: SendMessageResponse | SendStreamingMessageResponse,
    sid: str,
    request_id: str,
) -> None:
    """Processes a response from the A2A client, validates it, and emits events.

    Handles both success and error responses.
    """
    if isinstance(result.root, JSONRPCErrorResponse):
        error_data = result.root.error.model_dump(exclude_none=True)
        await _emit_debug_log(sid, request_id, 'error', error_data)
        await sio.emit(
            'chat response',
            {
                'response': f"Error: {error_data.get('message', 'Unknown error')}",
                'id': request_id,
            },
            to=sid,
        )
        return

    print(f"This is Resuts: {result}" )
    # Success case
    event = result.root.result
    kind = event.kind
    
    response_id = getattr(event, 'id', request_id)
    text_content = ""
    
    if kind == 'task':
        if event.status:
            text_content += "Agent Progress"        
    elif kind == "status-update":
        if event.status:
            text_content += extract_content(event.status.message.parts)     
    elif kind == "artifact-update":
        if event.artifact.parts:
            text_content += extract_content(event.artifact.parts)    
    elif kind == "message":
        if event.parts:
            text_content += extract_content(event.artifact.parts)  
    else:
        text_content += "random Text"
    
    # Get the option type for this session
    option_type = chat_sessions.get(sid, 'GENERAL')
    
    # Format response with collection_name prefix
    formatted_response = f"{option_type}\n{text_content}"
    
    # Emit in the format our frontend expects
    await sio.emit(
        'chat response', 
        {
            'response': formatted_response,
            'id': response_id
        }, 
        to=sid
    )
    
    # Also emit the detailed response for debugging
    try:
        response_data = event.model_dump(exclude_none=True)
        response_data['id'] = response_id
        await _emit_debug_log(sid, response_id, 'response', response_data)
    except Exception as e:
        logger.error(f"Failed to serialize response for debug log: {e}")
        # Still try to emit something useful
        await _emit_debug_log(
            sid, 
            response_id, 
            'response', 
            {'error': 'Failed to serialize complete response', 'type': str(type(event))}
        )


def get_card_resolver(
    client: httpx.AsyncClient, agent_card_url: str
) -> A2ACardResolver:
    """Returns an A2ACardResolver for the given agent card URL."""
    parsed_url = urlparse(agent_card_url)
    base_url = f'{parsed_url.scheme}://{parsed_url.netloc}'
    path_with_query = urlunparse(
        ('', '', parsed_url.path, '', parsed_url.query, '')
    )
    card_path = path_with_query.lstrip('/')
    if card_path:
        card_resolver = A2ACardResolver(
            client, base_url, agent_card_path=card_path
        )
    else:
        card_resolver = A2ACardResolver(client, base_url)

    return card_resolver

# ==============================================================================
# Direct static file routes for CSS and JS
# ==============================================================================

@app.get('/styles.css')
async def get_css():
    """Directly serve the CSS file."""
    css_path = os.path.join(current_dir, "styles.css")
    if not os.path.exists(css_path):
        raise HTTPException(status_code=404, detail="CSS file not found")
    return FileResponse(css_path, media_type="text/css")


@app.get('/script.js')
async def get_js():
    """Directly serve the JavaScript file."""
    js_path = os.path.join(current_dir, "script.js")
    if not os.path.exists(js_path):
        raise HTTPException(status_code=404, detail="JavaScript file not found")
    return FileResponse(js_path, media_type="application/javascript")


# ==============================================================================
# Script Management Routes
# ==============================================================================

@app.get('/api/scripts')
async def list_scripts():
    """List all JavaScript automation scripts in the scripts folder."""
    scripts_dir = os.path.join(current_dir, "scripts")
    
    # Create scripts directory if it doesn't exist
    if not os.path.exists(scripts_dir):
        os.makedirs(scripts_dir)
        
    scripts = []
    try:
        # List all .js files in the scripts directory
        for file in os.listdir(scripts_dir):
            if file.endswith('.js'):
                scripts.append(file)
        return {"scripts": scripts}
    except Exception as e:
        logger.error(f"Error listing scripts: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post('/api/scripts/run')
async def run_script(request: Request):
    """Run a selected JavaScript automation script."""
    data = await request.json()
    script_name = data.get('script')
    
    if not script_name or not script_name.endswith('.js'):
        return JSONResponse(content={"error": "Invalid script name"}, status_code=400)
    
    # Ensure script exists and is in the scripts directory (security measure)
    scripts_dir = os.path.join(current_dir, "scripts")
    script_path = os.path.join(scripts_dir, script_name)
    
    if not os.path.exists(script_path):
        return JSONResponse(content={"error": f"Script {script_name} not found"}, status_code=404)
    
    try:
        # Run the script using Node.js with UTF-8 encoding
        process = subprocess.Popen(
            ['node', script_path], 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',  # Explicitly set encoding to UTF-8
            errors='replace'   # Replace any characters that can't be decoded
        )
        stdout, stderr = process.communicate(timeout=30)  # 30 second timeout
        
        return JSONResponse(content={
            "success": process.returncode == 0,
            "output": stdout,
            "error": stderr,
            "returncode": process.returncode
        })
    except subprocess.TimeoutExpired:
        return JSONResponse(content={"error": "Script execution timed out"}, status_code=408)
    except Exception as e:
        logger.error(f"Error running script {script_name}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get('/api/scripts/content')
async def get_script_content(script: str):
    """Get the content of a specific script file."""
    # Ensure script name is valid and has .js extension
    if not script or not script.endswith('.js'):
        return JSONResponse(content={"error": "Invalid script name"}, status_code=400)
    
    # Ensure script exists and is in the scripts directory (security measure)
    scripts_dir = os.path.join(current_dir, "scripts")
    script_path = os.path.join(scripts_dir, script)
    
    if not os.path.exists(script_path):
        return JSONResponse(content={"error": f"Script {script} not found"}, status_code=404)
    
    try:
        # Read the script content
        with open(script_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        return {"script": script, "content": content}
    except Exception as e:
        logger.error(f"Error reading script {script}: {e}")
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ==============================================================================
# FastAPI Routes for QaAgent Frontend
# ==============================================================================

@app.get('/', response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Serve the main index.html page."""
    try:
        # Add the current date and user data to the template context
        context = {
            'request': request,
            'current_date': '2025-08-17 18:28:49',  # As specified
            'current_user': 'DarrenDsaEG'           # As specified
        }
        return templates.TemplateResponse('index.html', context)
    except Exception as e:
        logger.error(f"Error rendering index template: {e}", exc_info=True)
        return HTMLResponse(content=f"<html><body>Error loading page: {e}</body></html>")


@app.get('/scripts', response_class=HTMLResponse)
@app.get('/scripts.html', response_class=HTMLResponse)
async def scripts_page(request: Request) -> HTMLResponse:
    """Serve the scripts management page."""
    try:
        # Add the current date and user data to the template context
        context = {
            'request': request
        }
        return templates.TemplateResponse('scripts.html', context)
    except Exception as e:
        logger.error(f"Error rendering scripts template: {e}", exc_info=True)
        return HTMLResponse(content=f"<html><body>Error loading page: {e}</body></html>")


@app.get('/udemy', response_class=HTMLResponse)
async def udemy_page(request: Request) -> HTMLResponse:
    """Serve the udemy page."""
    try:
        template_path = os.path.join(current_dir, 'udemy.html')
        logger.info(f"Loading template from: {template_path}")
        logger.info(f"Template exists: {os.path.exists(template_path)}")
        return templates.TemplateResponse('udemy.html', {'request': request})
    except Exception as e:
        logger.error(f"Error rendering udemy template: {e}", exc_info=True)
        return HTMLResponse(content=f"<html><body>Error loading page: {e}</body></html>")


@app.get('/amazon', response_class=HTMLResponse)
async def amazon_page(request: Request) -> HTMLResponse:
    """Serve the amazon page."""
    try:
        template_path = os.path.join(current_dir, 'amazon.html')
        logger.info(f"Loading template from: {template_path}")
        logger.info(f"Template exists: {os.path.exists(template_path)}")
        return templates.TemplateResponse('amazon.html', {'request': request})
    except Exception as e:
        logger.error(f"Error rendering amazon template: {e}", exc_info=True)
        return HTMLResponse(content=f"<html><body>Error loading page: {e}</body></html>")


@app.get('/general', response_class=HTMLResponse)
async def general_page(request: Request) -> HTMLResponse:
    """Serve the GENERAL page."""
    try:
        template_path = os.path.join(current_dir, 'general.html')
        logger.info(f"Loading template from: {template_path}")
        logger.info(f"Template exists: {os.path.exists(template_path)}")
        return templates.TemplateResponse('general.html', {'request': request})
    except Exception as e:
        logger.error(f"Error rendering general template: {e}", exc_info=True)
        return HTMLResponse(content=f"<html><body>Error loading page: {e}</body></html>")


@app.get('/udemy.html', response_class=RedirectResponse)
async def udemy_redirect() -> RedirectResponse:
    """Redirect .html URLs to clean URLs"""
    return RedirectResponse(url='/udemy')


@app.get('/amazon.html', response_class=RedirectResponse)
async def amazon_redirect() -> RedirectResponse:
    """Redirect .html URLs to clean URLs"""
    return RedirectResponse(url='/amazon')


@app.get('/general.html', response_class=RedirectResponse)
async def general_redirect() -> RedirectResponse:
    """Redirect .html URLs to clean URLs"""
    return RedirectResponse(url='/general')


@app.post('/agent-card')
async def get_agent_card(request: Request) -> JSONResponse:
    """Fetch and validate the agent card from a given URL."""
    # 1. Parse request and get sid. If this fails, we can't do much.
    try:
        request_data = await request.json()
        agent_url = request_data.get('url')
        sid = request_data.get('sid')

        if not agent_url or not sid:
            return JSONResponse(
                content={'error': 'Agent URL and SID are required.'},
                status_code=400,
            )
    except Exception as e:
        logger.warning(f'Failed to parse JSON from /agent-card request: {e}')
        return JSONResponse(
            content={'error': 'Invalid request body.'}, status_code=400
        )

    # Extract custom headers from the request
    custom_headers = {
        name: value
        for name, value in request.headers.items()
        if name.lower() not in STANDARD_HEADERS
    }

    # 2. Log the request.
    await _emit_debug_log(
        sid,
        'http-agent-card',
        'request',
        {
            'endpoint': '/agent-card',
            'payload': request_data,
            'custom_headers': custom_headers,
        },
    )

    # 3. Perform the main action and prepare response.
    try:
        async with httpx.AsyncClient(
            timeout=30.0, headers=custom_headers
        ) as client:
            card_resolver = get_card_resolver(client, agent_url)
            card = await card_resolver.get_agent_card()

        card_data = card.model_dump(exclude_none=True)
        validation_errors = validators.validate_agent_card(card_data)
        response_data = {
            'card': card_data,
            'validation_errors': validation_errors,
        }
        response_status = 200

    except httpx.RequestError as e:
        logger.error(
            f'Failed to connect to agent at {agent_url}', exc_info=True
        )
        response_data = {'error': f'Failed to connect to agent: {e}'}
        response_status = 502  # Bad Gateway
    except Exception as e:
        logger.error('An internal server error occurred', exc_info=True)
        response_data = {'error': f'An internal server error occurred: {e}'}
        response_status = 500

    # 4. Log the response and return it.
    await _emit_debug_log(
        sid,
        'http-agent-card',
        'response',
        {'status': response_status, 'payload': response_data},
    )
    return JSONResponse(content=response_data, status_code=response_status)


# ==============================================================================
# Socket.IO Event Handlers
# ==============================================================================

@sio.on('connect')
async def handle_connect(sid: str, environ: dict[str, Any]) -> None:
    """Handle the 'connect' socket.io event."""
    logger.info(f'Client connected: {sid}')
    logger.info(f'Connection info: {environ.get("HTTP_USER_AGENT")}')
    logger.info(f'Headers: {dict([(k,v) for k,v in environ.items() if k.startswith("HTTP_")])}')
    
    # Default initialization for a quick demo - point to a default agent URL
    # This would be replaced with proper initialization in production
    try:
        agent_url = "http://localhost:10001/"  # Default to host agent
        httpx_client = httpx.AsyncClient(timeout=600.0)
        card_resolver = get_card_resolver(httpx_client, agent_url)
        card = await card_resolver.get_agent_card()
        a2a_client = A2AClient(httpx_client, agent_card=card)
        clients[sid] = (httpx_client, a2a_client, card)
        logger.info(f"Auto-initialized client for {sid}")
    except Exception as e:
        logger.error(f"Failed to auto-initialize client: {e}", exc_info=True)


@sio.on('disconnect')
async def handle_disconnect(sid: str) -> None:
    """Handle the 'disconnect' socket.io event."""
    logger.info(f'Client disconnected: {sid}')
    if sid in clients:
        httpx_client, _, _ = clients.pop(sid)
        await httpx_client.aclose()
        logger.info(f'Cleaned up client for {sid}')
    
    # Clean up session data
    if sid in chat_sessions:
        del chat_sessions[sid]
    if sid in welcome_sent:
        del welcome_sent[sid]


@sio.on('join')
async def handle_join(sid: str, data: dict[str, Any]) -> None:
    """Handle the 'join' socket.io event - for tracking which option the user selected."""
    option = data.get('option')
    logger.info(f"Join request received with data: {data}")
    
    if option:
        chat_sessions[sid] = option
        logger.info(f"Client {sid} joined with option: {option}")
        
        # Check if welcome message has already been sent for this session
        if sid not in welcome_sent or not welcome_sent[sid]:
            # Show typing indicator
            await sio.emit('user typing', {}, to=sid)
            
            # Small delay to make typing indicator more realistic
            import asyncio
            await asyncio.sleep(0.5)
            
            # Send welcome message with collection_name format
            welcome_text = f"{option}\nWelcome to the {option} service. How can I help you today?"
            await sio.emit('chat response', {
                'response': welcome_text,
                'id': str(uuid4())
            }, to=sid)
            
            # Hide typing indicator
            await sio.emit('user stop typing', {}, to=sid)
            
            # Mark that we've sent the welcome message
            welcome_sent[sid] = True
            logger.info(f"Sent welcome message to {sid}")


@sio.on('initialize_client')
async def handle_initialize_client(sid: str, data: dict[str, Any]) -> None:
    """Handle the 'initialize_client' socket.io event."""
    agent_card_url = data.get('url')
    logger.info(f"Initialize client request with URL: {agent_card_url}")

    custom_headers = data.get('customHeaders', {})

    if not agent_card_url:
        await sio.emit(
            'client_initialized',
            {'status': 'error', 'message': 'Agent URL is required.'},
            to=sid,
        )
        return
        
    try:
        httpx_client = httpx.AsyncClient(timeout=600.0, headers=custom_headers)
        card_resolver = get_card_resolver(httpx_client, agent_card_url)
        card = await card_resolver.get_agent_card()
        a2a_client = A2AClient(httpx_client, agent_card=card)
        clients[sid] = (httpx_client, a2a_client, card)
        await sio.emit('client_initialized', {'status': 'success'}, to=sid)
        logger.info(f"Client {sid} initialized successfully")
    except Exception as e:
        logger.error(
            f'Failed to initialize client for {sid}: {e}', exc_info=True
        )
        await sio.emit(
            'client_initialized', {'status': 'error', 'message': str(e)}, to=sid
        )


@sio.on('chat message')
async def handle_chat_message(sid: str, data: dict[str, Any]) -> None:
    """Handle chat messages from QaAgent frontend."""
    # Log the raw data to help with debugging
    logger.info(f"Received raw data from {sid}: {data}")
    
    # Accept both 'query' and 'message' for compatibility
    user_query = bleach.clean(data.get('query') or data.get('message', ''))
    option_type = data.get('option', chat_sessions.get(sid, 'GENERAL'))
    
    # Store the option type in the session
    chat_sessions[sid] = option_type
    
    message_id = str(uuid4())
    
    logger.info(f"Processing message from {sid}: {option_type} - {user_query}")
    
    if not user_query:
        logger.warning(f"Empty message received from {sid}")
        await sio.emit(
            'chat response',
            {'response': f"\nPlease enter a message.", 'id': message_id},
            to=sid,
        )
        return
    
    if sid not in clients:
        # Try to initialize the client if it doesn't exist
        try:
            agent_url = "http://localhost:10001/"  # Default to host agent
            logger.info(f"Auto-initializing client for {sid} with URL: {agent_url}")
            httpx_client = httpx.AsyncClient(timeout=600.0)
            card_resolver = get_card_resolver(httpx_client, agent_url)
            card = await card_resolver.get_agent_card()
            a2a_client = A2AClient(httpx_client, agent_card=card)
            clients[sid] = (httpx_client, a2a_client, card)
            logger.info(f"Successfully auto-initialized client for {sid}")
        except Exception as e:
            logger.error(f"Failed to initialize client for {sid}: {e}")
            await sio.emit(
                'chat response',
                {'response': f'\nFailed to connect to agent: {e}', 'id': message_id},
                to=sid,
            )
            return
    
    _, a2a_client, card = clients[sid]
    
    # Format message with option type included
    formatted_message = f"{option_type} {user_query}"
    
    message = Message(
        role=Role.user,
        parts=[TextPart(text=formatted_message)],  # Include option type in the message
        message_id=message_id,
    )
    payload = MessageSendParams(
        message=message,
        configuration=MessageSendConfiguration(accepted_output_modes=['text/plain']),
    )
    
    # Show typing indicator
    await sio.emit('user typing', {}, to=sid)

    try:
        # Check if streaming is supported
        supports_streaming = (
            hasattr(card.capabilities, 'streaming')
            and card.capabilities.streaming is True
        )
        
        if supports_streaming:
            logger.info(f"Using streaming mode for {sid}")
            stream_request = SendStreamingMessageRequest(
                id=message_id,
                method='message/stream',
                jsonrpc='2.0',
                params=payload,
            )
            
            response_stream = a2a_client.send_message_streaming(stream_request)
            
            async for stream_result in response_stream:
                # Log the structure of the response for debugging
                if hasattr(stream_result.root, 'result'):
                    result_type = type(stream_result.root.result).__name__
                    logger.info(f"Received streaming response of type: {result_type}")
                    
                await _process_a2a_response(stream_result, sid, message_id)
        else:
            logger.info(f"Using non-streaming mode for {sid}")
            send_message_request = SendMessageRequest(
                id=message_id,
                method='message/send',
                jsonrpc='2.0',
                params=payload,
            )
            send_result = await a2a_client.send_message(send_message_request)
            await _process_a2a_response(send_result, sid, message_id)
    
    except Exception as e:
        logger.error(f'Failed to send message: {e}', exc_info=True)
        await sio.emit(
            'chat response',
            {'response': f'\nError: {str(e)}', 'id': message_id},
            to=sid,
        )
    finally:
        # Stop typing indicator
        await sio.emit('user stop typing', {}, to=sid)


# ==============================================================================
# Main Execution
# ==============================================================================

if __name__ == '__main__':
    import uvicorn

    # NOTE: The 'reload=True' flag is for development purposes only.
    # In a production environment, use a proper process manager like Gunicorn.
    uvicorn.run('app:app', host='127.0.0.1', port=5001, reload=True)
import os
import pathlib
import requests
from uuid import UUID, uuid4
from fastapi import FastAPI,Request,Form,HTTPException,Response,Depends
from fastapi.responses import HTMLResponse,RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.session_verifier import SessionVerifier
from firebase import Firebase
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
from pydantic import BaseModel
import google.auth.transport.requests


cookie_params = CookieParameters()

# Uses UUID
cookie = SessionCookie(
    cookie_name="state",
    identifier="general_verifier",
    auto_error=True,
    secret_key="DONOTUSE",
    cookie_params=cookie_params,
)
_cookie = SessionCookie(
    cookie_name="data",
    identifier="general_verifier",
    auto_error=True,
    secret_key="sdfgfgfdgv",
    cookie_params=cookie_params,
)

class SessionData(BaseModel):
    state: str
  
class LoginData(BaseModel):
    google_id: str
    name:str
  

  



backend = InMemoryBackend[UUID, SessionData]()
class BasicVerifier(SessionVerifier[UUID, SessionData]):
    def __init__(
        self,
        *,
        identifier: str,
        auto_error: bool,
        backend: InMemoryBackend[UUID, SessionData],
        auth_http_exception: HTTPException,
    ):
        self._identifier = identifier
        self._auto_error = auto_error
        self._backend = backend
        self._auth_http_exception = auth_http_exception

    @property
    def identifier(self):
        return self._identifier

    @property
    def backend(self):
        return self._backend

    @property
    def auto_error(self):
        return self._auto_error

    @property
    def auth_http_exception(self):
        return self._auth_http_exception

    def verify_session(self, model: SessionData) -> bool:
        """If the session exists, it is valid"""
        return True


verifier = BasicVerifier(
    identifier="general_verifier",
    auto_error=True,
    backend=backend,
    auth_http_exception=HTTPException(status_code=403, detail="invalid session"),
)



app = FastAPI()
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = "1096808373982-m1c38d9al9f1re8sr8r18fo6ngmnjknk.apps.googleusercontent.com"
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")



flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)


firebaseConfig = {
   "apiKey": "AIzaSyCDExjmv1SNg1sdbggRXuvFUK1I_S1NRys",
  "authDomain": "shaped-faculty-376509.firebaseapp.com",
  "projectId": "shaped-faculty-376509",
  "storageBucket": "shaped-faculty-376509.appspot.com",
  "messagingSenderId": "1096808373982",
  "appId": "1:1096808373982:web:d291424661e30fdd23ec4f",
  "measurementId": "G-3LEE8XL7N4",
  "databaseURL":"https://shaped-faculty-376509-default-rtdb.firebaseio.com/"
}
firebase = Firebase(firebaseConfig)
db = firebase.database()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")



@app.get("/",response_class=HTMLResponse)
async def start(request: Request,response:HTMLResponse):
    if await backend.read("login"):
        return RedirectResponse("/dashboard",status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/login",response_class=HTMLResponse)
async def login(request: Request,response: HTMLResponse):
    authorization_url, state = flow.authorization_url()

    session = uuid4()
    data = SessionData(state=state)
    await backend.create(session, data)
    cookie.attach_to_response(response, session)

    return f"""<a href="{authorization_url}"><button type="button" >Authorize</button></a>"""

@app.get("/dashboard")
async def dashboard(request:Request):
    if await backend.read("login"):
        loginCred = await backend.read("login")
        data = db.child("data").child(loginCred.google_id).get().val()
        return templates.TemplateResponse("index.html", {"request": request,"data":data,"name":loginCred.name})
    return RedirectResponse("/",status_code=303)

@app.post("/dashboard")
async def addTask(request:Request,task_name: str = Form()):
    if await backend.read("login"):
        login_cred = await backend.read("login")
        db.child("data").child(login_cred.google_id).push(task_name)
        data = db.child("data").child(login_cred.google_id).get().val()
        return templates.TemplateResponse("index.html", {"request": request,"data":data,"name":login_cred.name})
    return RedirectResponse("/",status_code=303)
    
   
@app.post("/deleteTask")
async def addTask(request:Request,taskId: str = Form()):
    if await backend.read("login"):
        login_cred = await backend.read("login")
        db.child("data").child(login_cred.google_id).child(taskId).remove()
        return RedirectResponse("/dashboard",status_code=303)
    return RedirectResponse("/",status_code=303)

@app.post("/updateTask")
async def addTask(request:Request,taskId: str = Form(),task_name: str = Form()):
    if await backend.read("login"):
        login_cred = await backend.read("login")
        db.child("data").child(login_cred.google_id).child(taskId).set(task_name)
        return RedirectResponse("/dashboard",status_code=303)
    return RedirectResponse("/",status_code=303)

@app.get("/callback")
async def callback(request: Request,state:str,response:RedirectResponse):
    flow.fetch_token(authorization_response=request.url._url)
    # if not await backend.read("state") == request.args["state"]:
    #     return "Unauthorized Access"

    credentials = flow.credentials
    
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )
    print(id_info)
    # session = uuid4()
    # data = _SessionData(name=id_info.get("name"),google_id=id_info.get("sub"))
    # await backend.create(session, data)
    # _cookie.attach_to_response(response, session)
    await backend.create("login",LoginData(google_id=id_info.get("sub"),name=id_info.get("name")))
    if  db.child("users").child(id_info.get("sub")).get().val() is None:
        db.child("users").child(id_info.get("sub")).push({"name":id_info.get("name"),"email":id_info.get("email")})
    # session["google_id"] = id_info.get("sub")
    # session["name"] = id_info.get("name")
    return RedirectResponse("/dashboard",status_code=303)

@app.get("/logout")
async def logout():
    await backend.delete("login")
    return RedirectResponse("/",status_code=303)

@app.get("/infog")
async def infog(response: Response, session_id: UUID = Depends(cookie)):
    data  = await backend.create("mbsa",SessionData(state="mbsambsa"))
    return session_id

@app.get("/read")
async def read(response: Response, session_id: UUID = Depends(cookie)):
    data  = await backend.read("login")
    return data.google_id

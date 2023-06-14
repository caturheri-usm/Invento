import pyrebase, re, json
from firebase_admin import auth, credentials, firestore_async, initialize_app, firestore
from fastapi.responses import JSONResponse
from fastapi import FastAPI, HTTPException, Depends
from fastapi_cloudauth.firebase import FirebaseCurrentUser, FirebaseClaims
from google.cloud.firestore_v1.base_query import FieldFilter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import tensorflow as tf
from typing import List
import numpy as np

# tambahkan model ke direktori model dengan nama model.h5
#model = tf.keras.models.load_model("model/model.h5")

# Inisialisasi aplikasi Firebase
cred = credentials.Certificate("./key.json")
initialize_app(cred)
db = firestore_async.client()

app = FastAPI(
    title="Invento Flow App",
    description="API ini dibangun menggunakan FastAPI dan digunakan untuk menciptakan alur app invento ke mobile client.",
    version="1.0.0",
)

with open("firebase_config.json") as f:
    firebase_config = json.load(f)
project_id = firebase_config["projectId"]
get_current_user = FirebaseCurrentUser(project_id=project_id)

py = pyrebase.initialize_app(json.load(open("firebase_config.json")))
pb = py.auth()

# Model data register request
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class FormRegister(BaseModel):
    name: str
    tag: list[str]
    desc: str


# Model data loginrequest
class LoginRequest(BaseModel):
    email: str
    password: str


class ResetPassword(BaseModel):
    email: str


class UserUpdate(BaseModel):
    name: str
    tag: list[str]
    desc: str


class CreateProject(BaseModel):
    name: str
    tag: list[str]
    desc: str


class ProjectUpdate(BaseModel):
    name: str
    tag: list[str]
    desc: str


class UserInfo(BaseModel):
    status: bool
    msg: str


# Endpoint untuk registrasi pengguna baru
@app.post(
    "/register",
    summary="User melakukan registrasi.",
    description="isi request body seperti dibawah ini lalu akan menghasilkan user_id dan token. **setelah register, tampilkan halaman untuk melakukan verifikasi email user**",
    tags=["Auth"],
)
async def register(register: RegisterRequest):
    username = register.username
    email = register.email
    password = register.password
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise HTTPException(status_code=400, detail="Invalid email format.")
    elif not re.match(
        r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$", password
    ):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters, including at least one letter, one number, and one special character.",
        )
    try:
        auth.get_user_by_email(email)
        raise HTTPException(
            detail={"message": "Error! Email already exists"}, status_code=400
        )
    except auth.UserNotFoundError:
        try:
            users_collection = db.collection("users")
            query = users_collection.where(filter=FieldFilter("username", "==", username)).limit(1)
            query_results = await query.get()
            if len(query_results) > 0:
                raise HTTPException(
                    status_code=400, detail={"message": "Username already exists."}
                )
            user = pb.create_user_with_email_and_password(email, password)
            uid = user.get("localId")
            user = pb.refresh(user["refreshToken"])
            token = user["idToken"]
            pb.send_email_verification(token)
            user_data = {"username": username}
            await users_collection.document(uid).set(user_data)
            return JSONResponse(
                content={
                    "message": "Registration successful. Please check your email for verification.",
                    "id_user": uid,
                    "token": token,
                },
                status_code=200,
            )
        except:
            raise HTTPException(
                status_code=400, detail={"message": "Error registering user"}
            )


# endpoint form user register
@app.post(
    "/form-register",
    tags=["Users"],
    summary="User melakukan pengisian data",
    description="setelah register dan verifikasi email, user diarahkan untuk melakukan pengisian data seperti **name**, **tags**, **desc**",
)
async def formRegister(
    form: FormRegister, current_user: FirebaseClaims = Depends(get_current_user)
):
    name = form.name
    tag = form.tag
    desc = form.desc
    email = current_user.email
    if not name or not tag:
        raise HTTPException(status_code=400, detail="Please fill out the field.")
    elif len(tag) != len(set(tag)):
        raise HTTPException(status_code=400, detail="Nilai dalam array tag harus unik")
    try:
        uid = current_user.user_id
        users_collection = db.collection("users")
        user_doc = await users_collection.document(uid).get()
        if user_doc.exists:
            username = user_doc.get("username")
        else:
            username = ""
        user_data = {"username": username, "email": email, "name": name, "tag": tag, "desc": desc}
        await users_collection.document(uid).set(user_data)
        return JSONResponse(
            content={"message": "Data user berhasil disimpan.", "user": user_data},
            status_code=200,
        )
    except:
        raise HTTPException(
            status_code=400, detail={"message": "Gagal menyimpan data user."}
        )


# Endpoint login
@app.post(
    "/login",
    summary="User melakukan Login.",
    description="isi request body seperti dibawah ini lalu akan menghasilkan user_id dan token.",
    tags=["Auth"],
)
async def login(login: LoginRequest):
    email = login.email
    password = login.password
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required.")
    try:
        user = pb.sign_in_with_email_and_password(email, password)
        uid = user.get("localId")
        user = pb.refresh(user["refreshToken"])
        token = user["idToken"]
        return JSONResponse(
            content={"message": "Login successful", "id_user": uid, "token": token},
            status_code=200,
        )
    except:
        raise HTTPException(status_code=400, detail="Incorrect Email or Password")


# Endpoint reset-password
@app.post(
    "/reset-password",
    summary="User melakukan Reset Password.",
    description="User akan menerima email untuk melakukan pembaruan kata sandi",
    tags=["Auth"],
)
async def resetPassword(request: ResetPassword):
    email = request.email
    if not email:
        raise HTTPException(status_code=400, detail="Email cannot be empty")
    try:
        pb.send_password_reset_email(email)
        return JSONResponse(
            content={"message": "Password reset email has been sent."}, status_code=200
        )
    except:
        raise HTTPException(detail="Internal Server Error", status_code=500)


# Endpoint protected_route
@app.get("/current", include_in_schema=False)
async def current(current_user: FirebaseClaims = Depends(get_current_user)):
    uid = current_user.user_id
    email = current_user.email
    return JSONResponse(
        content={"uid": uid, "email": email},
        status_code=200,
    )


@app.get(
    "/users",
    tags=["Users"],
    summary="menampilkan semua data users",
    description="menampilkan seluruh data users yang telah melakukan registrasi dan pengisian form-register",
)
async def get_users(current_user: FirebaseClaims = Depends(get_current_user)):
    try:
        users_ref = db.collection("users").stream()
        users = []
        async for user in users_ref:
            user_data = user.to_dict()
            user_data["uid"] = user.id
            users.append(user_data)
        if len(users) == 0:
            raise HTTPException(status_code=404, detail="Users not found")
        return JSONResponse(content={"users": users}, status_code=200)
    except:
        raise HTTPException(status_code=500, detail="Internal server error")


# Endpoint untuk mendapatkan profil user berdasarkan id
@app.get(
    "/usersbyid",
    tags=["Users"],
    summary="Menampilkan data users berdasarkan ID",
    description="untuk menampilkan data profil jika user klik profil pengguna lain.",
)
async def get_user_by_id(
    user_id: str, current_user: FirebaseClaims = Depends(get_current_user)
):
    try:
        doc_ref = db.collection("users").document(user_id)
        user_doc = await doc_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return {"user": user_data}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get(
    "/profile",
    tags=["Profile"],
    summary="Menampilkan data profile user",
    description="digunakan untuk melihat data profil user.",
)
async def get_profile(current_user: FirebaseClaims = Depends(get_current_user)):
    try:
        user_id = current_user.user_id
        doc_ref = db.collection("users").document(user_id)
        user_doc = await doc_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            return {"user": user_data}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except:
        raise HTTPException(status_code=500, detail="Internal Server Error")


# Endpoint untuk mengubah profil user berdasarkan id
@app.put(
    "/profile",
    tags=["Profile"],
    summary="Mengubah data profile users berdasarkan id",
    description="Dapat melakukan perubahan data profile user jika ingin mengubahnya.",
)
async def update_profile(
    update_user: UserUpdate,
    current_user: FirebaseClaims = Depends(get_current_user),
):
    if len(update_user.tag) != len(set(update_user.tag)):
        raise HTTPException(status_code=400, detail="Nilai dalam array tag harus unik")
    uid = current_user.user_id
    if not uid:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        doc_ref = db.collection("users").document(uid)
        await doc_ref.update(update_user.dict(exclude_unset=True))
        return JSONResponse(
            content={"message": "Profil pengguna berhasil diperbarui"}, status_code=200
        )
    except:
        raise HTTPException(status_code=400, detail="Failed to Update Profile")


# Endpoint untuk membuat proyek baru
@app.post(
    "/projects",
    tags=["Proyek"],
    summary="User membuat proyek baru",
    description="Data yang disi berupa nama proyek, tags menggunakan array, dan description project",
)
async def create_project(
    project: CreateProject, current_user: FirebaseClaims = Depends(get_current_user)
):
    if len(project.tag) != len(set(project.tag)):
        raise HTTPException(status_code=400, detail="Nilai dalam array tag harus unik")
    uid = current_user.user_id
    project_data = project.dict()
    if not project_data.get("name"):
        raise HTTPException(status_code=400, detail="Name are required.")
    elif not project_data.get("tag"):
        raise HTTPException(status_code=400, detail="Tag are required.")
    elif not project_data.get("desc"):
        raise HTTPException(status_code=400, detail="Description are required.")
    try:
        user_ref = await db.collection("users").document(uid).get()
        if user_ref.exists:
            user_data = user_ref.to_dict()
            created_by_name = user_data.get("name")
            project_data["createdById"] = uid
            project_data["createdByName"] = created_by_name
            new_project_ref = db.collection("projects").document()
            await new_project_ref.set(project_data)
            new_project_id = new_project_ref.id
            return JSONResponse(
                content={
                    "message": "Project created successfully",
                    "id": new_project_id,
                },
                status_code=200,
            )
    except:
        raise HTTPException(status_code=400, detail="Failed to Create Project.")


# Endpoint untuk mendapatkan daftar proyek
@app.get(
    "/projects",
    tags=["Proyek"],
    summary="User melihat semua daftar proyek",
    description="dapat digunakan didashboard atau beranda untuk menampilkan semua proyek yang telah dibuat oleh users",
)
async def get_projects(current_user: FirebaseClaims = Depends(get_current_user)):
    projects_ref = db.collection("projects").stream()
    projects = []
    async for project in projects_ref:
        project_data = project.to_dict()
        created_by = project_data.get("createdById")
        user_ref = db.collection("users").document(created_by)
        user_doc = await user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            project_info = {
                "project_id": project.id,
                "name": project_data.get("name"),
                "tag": project_data.get("tag"),
                "desc": project_data.get("desc"),
                "createdByName": user_data.get("name"),
                "createdById": project_data.get("createdById"),
            }
            projects.append(project_info)
    if len(projects) == 0:
        raise HTTPException(status_code=404, detail="Projects not found")
    return JSONResponse(content={"projects": projects}, status_code=200)


# endpoint untuk mengambil proyek berdasarkan id
@app.get(
    "/projects/{project_id}",
    tags=["Proyek"],
    summary="User melihat detail proyek tertentu",
    description="melakukan pengambilan detail proyek yang telah users buat",
)
async def get_project_by_id(
    project_id: str, current_user: FirebaseClaims = Depends(get_current_user)
):
    try:
        project_doc = await db.collection("projects").document(project_id).get()
        if project_doc.exists:
            project_data = project_doc.to_dict()
            user_id = current_user.user_id
            interaction_data = {"id_user": user_id, "id_proyek": project_id}
            await db.collection("interactions").add(interaction_data)
            return JSONResponse(content=project_data, status_code=200)
        else:
            raise HTTPException(status_code=404, detail="Project not found")
    except:
        raise HTTPException(status_code=500, detail=("Internal Message Error"))


@app.put(
    "/projects/{project_id}",
    tags=["Admin-Proyek"],
    summary="admin proyek melakukan perubahan data proyek tertentu",
    description="digunakan untuk edit data oleh admin proyek jika mengalami perubahan data",
)
async def update_project(
    project_id: str,
    update_project: ProjectUpdate,
    current_user: FirebaseClaims = Depends(get_current_user),
):
    try:
        uid = current_user.user_id
        doc_ref = db.collection("projects").document(project_id)
        project_doc = await doc_ref.get()
        if not project_doc.exists:
            raise HTTPException(status_code=404, detail="Project not found")
        project_data = project_doc.to_dict()
        if project_data.get("createdById") != uid:
            raise HTTPException(status_code=403, detail="Access denied")
        await doc_ref.update(update_project.dict())
        updated_project_doc = await doc_ref.get()
        updated_project_data = updated_project_doc.to_dict()
        return JSONResponse(
            content={
                "message": "Project updated successfully",
                "project": updated_project_data,
            },
            status_code=200,
        )
    except:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete(
    "/projects/{project_id}",
    tags=["Admin-Proyek"],
    summary="admin proyek melakukan penghapusan proyek tertentu",
    description="admin proyek melakukan penghapusan proyek tertentu berdasarkan project_id",
)
async def delete_project(
    project_id: str, current_user: FirebaseClaims = Depends(get_current_user)
):
    try:
        uid = current_user.user_id
        doc_ref = db.collection("projects").document(project_id)
        project = await doc_ref.get()
        if not project.exists:
            raise HTTPException(status_code=404, detail="")
        project_data = project.to_dict()
        created_by = project_data.get("createdById")
        if created_by != uid:
            raise HTTPException(status_code=403, detail="")
        await doc_ref.delete()
        return JSONResponse(
            content={"message": "Project successfully deleted"}, status_code=200
        )
    except:
        raise HTTPException(status_code=404, detail="Project Not Found.")


@app.post(
    "/projects/{project_id}/join",
    tags=["Proyek"],
    summary="Users melakukan join pada projek tertentu berdasarkan id",
    description="Users yang tertarik dapat bergabung dengan projek tertentu berdasarkan id proyek.",
)
async def join_project(
    project_id: str, current_user: FirebaseClaims = Depends(get_current_user)
):
    user_id = current_user.user_id
    project_ref = db.collection("projects").document(project_id)
    project = await project_ref.get()
    if project.exists:
        join_requests_ref = db.collection("join_requests")
        join_request_query = join_requests_ref.where(filter=FieldFilter("project_id", "==", project_id)).where(filter=FieldFilter("user_id", "==", user_id))
        existing_requests = []
        async for request_doc in join_request_query.stream():
            existing_requests.append(request_doc)
        if existing_requests:
            raise HTTPException(status_code=400, detail="User has already sent a join request.")
        project_data = project.to_dict()
        created_by = project_data.get("createdById")
        if created_by == user_id:
            raise HTTPException(status_code=403, detail="Cannot join your own project.")
        join_request_doc = db.collection("join_requests").document()
        users_ref = db.collection("users").document(user_id)
        user_data = await users_ref.get()
        if user_data.exists:
            user_name = user_data.get("name")
            project_name = project.get("name")
        else:
            raise HTTPException(status_code=404, detail="User not found")
        join_request_data = {
            "project_id": project_id,
            "user_id": user_id,
            "status": False,
            "message": f"{user_name} requests to join your {project_name} project.",
        }
        await join_request_doc.set(join_request_data)
        return JSONResponse(
            content={"message": "Join request has been sent"}, status_code=200
        )
    else:
        raise HTTPException(status_code=404, detail="Project not found")


@app.get(
    "/projects/{project_id}/join",
    tags=["Admin-Proyek"],
    summary="admin proyek melihat daftar permintaan join pada proyek buatannya.",
    description="admin proyek melihat daftar permintaan bergabung pada proyek yang dibuatnya.",
)
async def get_join_requests(
    project_id: str,
    current_user: FirebaseClaims = Depends(get_current_user),
):
    admin_id = current_user.user_id
    project_ref = db.collection("projects").document(project_id)
    project_snapshot = await project_ref.get()
    if (
        project_snapshot.exists
        and project_snapshot.to_dict().get("createdById") == admin_id
    ):
        join_requests_ref = db.collection("join_requests")
        join_requests_query = join_requests_ref.where(
            filter=FieldFilter("project_id", "==", project_id)
        ).where(filter=FieldFilter("status", "==", False))
        join_requests = []
        async for request_doc in join_requests_query.stream():
            request_data = request_doc.to_dict()
            pending_request = {
                "id": request_doc.id,
                "project_id": request_data["project_id"],
                "user_id": request_data["user_id"],
                "message": request_data.get("message"),
            }
            join_requests.append(pending_request)
        if not join_requests:
            raise HTTPException(status_code=404, detail="Join requests not found")
        return JSONResponse(content={"join_requests": join_requests}, status_code=200)
    else:
        raise HTTPException(status_code=403, detail="Access denied")


@app.post(
    "/projects/{project_id}/join/{request_id}",
    tags=["Admin-Proyek"],
    summary="admin proyek melakukan konfirmasi dari permintaan user yang join",
    description="berguna untuk menyeleksi mana saja user yang disetujui atau ditolak bergabung didalam proyek dibuatnya. jika **status**:**false**, maka permintaan ditolak. jika **status**:**true**, maka permintaan diterima.",
)
async def process_join_request(
    project_id: str,
    request_id: str,
    confirm: UserInfo,
    current_user: FirebaseClaims = Depends(get_current_user),
):
    admin_id = current_user.user_id
    status = confirm.status
    msg = confirm.msg
    project_ref = db.collection("projects").document(project_id)
    join_request_ref = db.collection("join_requests").document(request_id)
    project = await project_ref.get()
    if not project.exists or project.to_dict().get("createdById") != admin_id:
        raise HTTPException(status_code=403, detail="Access denied")
    join_request = await join_request_ref.get()
    if not join_request.exists:
        raise HTTPException(status_code=404, detail="Join request not found")
    await join_request_ref.update({"status": status, "message": msg})
    if status:
        join_request_data = join_request.to_dict()
        user_id = join_request_data["user_id"]
        await project_ref.update({"members": firestore.ArrayUnion([user_id])})
        return JSONResponse(
            content={"message": "Join request accepted"}, status_code=200
        )
    else:
        return JSONResponse(
            content={"message": "Join request rejected"}, status_code=200
        )


@app.get(
    "/projects/{project_id}/members",
    tags=["Admin-Proyek"],
    summary="admin proyek bisa melihat daftar user yang telah disetujui untuk bergabung proyek yang dibuat",
    description="melihat semua daftar users yang telah disetujui bergabung pada admin proyek",
)
async def get_project_members(
    project_id: str,
    current_user: FirebaseClaims = Depends(get_current_user),
):
    try:
        project_ref = db.collection("projects").document(project_id)
        project_snapshot = await project_ref.get()
        if project_snapshot.exists:
            project_data = project_snapshot.to_dict()
            if current_user.user_id == project_data.get("createdById"):
                members = project_data.get("members", [])
                members_data = []
                for member_id in members:
                    user_ref = db.collection("users").document(member_id)
                    user_snapshot = await user_ref.get()
                    if user_snapshot.exists:
                        user_data = user_snapshot.to_dict()
                        member = {"id": member_id, "name": user_data.get("name")}
                        members_data.append(member)
                return {"members": members_data}
            else:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            raise HTTPException(status_code=404, detail="Project not found")
    except:
        raise HTTPException(status_code=500, detail=("Internal Server Error"))


@app.get(
    "/myprojects",
    tags=["Admin-Proyek"],
    summary="Melihat daftar proyek yang dibuat oleh admin-proyek",
    description="Endpoint untuk melihat daftar proyek yang telah dibuat oleh admin-proyek",
)
async def get_my_projects(current_user: FirebaseClaims = Depends(get_current_user)):
    admin = current_user.user_id
    projects_ref = (
        db.collection("projects")
        .where(filter=FieldFilter("createdById", "==", admin))
        .stream()
    )
    projects = []
    async for project in projects_ref:
        project_data = project.to_dict()
        project_data["project_id"] = project.id
        projects.append(project_data)
    if len(projects) == 0:
        raise HTTPException(status_code=404, detail="No projects found.")
    return {"projects": projects}


@app.get(
    "/myjoinrequests",
    tags=["Proyek"],
    summary="Users melihat daftar join requests terhadap project",
    description="Users yang telah melakukan join requests ke projek dapat dilihat melalui endpoint ini",
)
async def my_join_requests(current_user: FirebaseClaims = Depends(get_current_user)):
    user_id = current_user.user_id
    if not user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    join_requests_ref = (
        db.collection("join_requests")
        .where(filter=FieldFilter("user_id", "==", user_id))
        .stream()
    )
    join_requests = []
    async for join_request in join_requests_ref:
        join_request_data = join_request.to_dict()
        project_id = join_request_data.get("project_id")
        project_ref = db.collection("projects").document(project_id)
        project_snapshot = await project_ref.get()
        if project_snapshot.exists:
            project_data = project_snapshot.to_dict()
            join_request_info = {
                "join_request_id": join_request.id,
                "project_id": project_id,
                "project_name": project_data.get("name"),
                "message": join_request_data.get("message"),
                "status": join_request_data.get("status"),
            }
            join_requests.append(join_request_info)
    if not join_requests:
        raise HTTPException(detail="Join request not found", status_code=404)
    return {"join_requests": join_requests}


@app.delete(
    "/projects/{project_id}/members/{user_id}",
    tags=["Admin-Proyek"],
    summary="Admin-Proyek dapat menghapus anggota dari proyek",
    description="Menghapus anggota (members) dari proyek oleh admin proyek",
)
async def delete_project_member(
    project_id: str,
    user_id: str,
    current_user: FirebaseClaims = Depends(get_current_user),
):
    try:
        project_ref = db.collection("projects").document(project_id)
        project_snapshot = await project_ref.get()
        if project_snapshot.exists:
            project_data = project_snapshot.to_dict()
            if current_user.user_id == project_data.get("createdById"):
                members = project_data.get("members", [])
                if user_id in members:
                    members.remove(user_id)
                    await project_ref.update({"members": members})
                    return {
                        "message": "Member has been successfully removed from the project"
                    }
                else:
                    raise HTTPException(
                        status_code=404, detail="Member not found in project"
                    )
            else:
                raise HTTPException(status_code=403, detail="Access denied")
        else:
            raise HTTPException(status_code=404, detail="Project not found")
    except:
        raise HTTPException(status_code=500, detail=("Internal Server Error"))


@app.get("/recommendations", tags=["Rekomendasi"])
async def get_recommendations(current_user: FirebaseClaims = Depends(get_current_user)):
    try:
        user_id = current_user.user_id

        # Ambil koleksi interactions dari Firestore
        interactions_ref = db.collection("interactions")
        interactions_query = interactions_ref.where("id_user", "==", user_id)
        interactions_docs = await interactions_query.get()
        # interacted_projects menghasilkan interaksi id_proyek yang telah dilakukan oleh user_id
        interacted_projects = [doc.get("id_proyek") for doc in interactions_docs] 

        # Lakukan logika rekomendasi sesuai dengan dokumentasi yang diberikan
        # ...

        # Hasilkan daftar rekomendasi
        recommendations = []

        return {"user_id": user_id, "recommendations": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error") from e

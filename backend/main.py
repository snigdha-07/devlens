from fastapi import FastAPI,UploadFile,File
app=FastAPI()

@app.post("/upload")
async def upload_file(file: UploadFile=File(...)):
    return{
        "filename": file.filename,
        "type": file.content_type
    }

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

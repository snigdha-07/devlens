import { useState } from "react";

function App() {
  const [file, setFile] = useState(null);

  const handleUpload = async () => {
    if (!file) {
      alert("Select a file first");
      return;
    }
  
    const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    console.log("Response:", data);
  } catch (err) {
    console.error("Error:", err);
  }
    
  };

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "100vh"
    }}>
      <h1>Devlens - Upload Resume</h1>

      <input
        type="file"
        onChange={(e) => setFile(e.target.files[0])}
      />

      <button onClick={handleUpload} style={{ marginTop: "20px" }}>
        Upload
      </button>
    </div>
  );
}

export default App;
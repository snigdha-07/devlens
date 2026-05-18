import { useState } from "react";

function App() {
  const [resumeFile, setResumeFile] = useState(null);
  const [jdFile, setJdFile] = useState(null);

  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");

  const [resumeSkills, setResumeSkills] = useState([]);
  const [jdSkills, setJdSkills] = useState([]);

  const handleResumeUpload = async () => {
    if (!resumeFile) {
      alert("Select a file first");
      return;
    }
  
    const formData = new FormData();
  formData.append("file", resumeFile);

  try {
    const res = await fetch("http://127.0.0.1:8000/upload-resume", {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    setResumeSkills(data.skills || []);
    console.log("Response:", data);
  } catch (err) {
    console.error("Error:", err);
  }
    
  };

   const handleJDUpload = async () => {

    if (!jdFile) {
      alert("Please upload JD PDF");
      return;
    }


    const formData = new FormData();

    formData.append("title", title);
    formData.append("company", company);
    formData.append("file", jdFile);


    try {

      const res = await fetch("http://127.0.0.1:8000/add-jd", {
        method: "POST",
        body: formData,
      });


      const data = await res.json();
      console.log("JD Response:", data);

      setJdSkills(data.skills || []);

    } catch (err) {
      console.error(err);
    }
  };

 return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "#050101",
      }}
    >

      <div
        style={{
          width: "600px",
          background: "white",
          padding: "30px",
          borderRadius: "12px",
          boxShadow: "0px 0px 10px rgba(206, 206, 206, 0.23)",
          display: "flex",
          flexDirection: "column",
          gap: "20px"
        }}
      >
        <h1>Devlens</h1>


        <h2>Upload Resume</h2>

        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setResumeFile(e.target.files[0])}
        />

        <button onClick={handleResumeUpload}>
          Upload Resume
        </button>


        <div>
          <h3>Resume Skills:</h3>

          <ul>
            {resumeSkills.map((skill, index) => (
              <li key={index}>{skill}</li>
            ))}
          </ul>
      </div>
      <hr />


        <h2>Upload Job Description</h2>

        <input
          type="text"
          placeholder="Job Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />


        <input
          type="text"
          placeholder="Company"
          value={company}
          onChange={(e) => setCompany(e.target.value)}
        /><input
          type="file"
          accept="application/pdf"
          onChange={(e) => setJdFile(e.target.files[0])}
        />


        <button onClick={handleJDUpload}>
          Upload JD
        </button>


        <div>
          <h3>JD Skills:</h3>

          <ul>
            {jdSkills.map((skill, index) => (
              <li key={index}>{skill}</li>
            ))}
          </ul>
        </div>

      </div>
    </div>
 );
}

export default App;
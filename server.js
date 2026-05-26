const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");

const Student = require("./models/Student");

const app = express();

app.use(express.json());
app.use(cors());
app.use(express.static("public"));

// MongoDB Connection
mongoose.connect("mongodb://127.0.0.1:27017/studentDB")
.then(() => {
    console.log("MongoDB Connected");
})
.catch((err) => {
    console.log(err);
});

// HOME ROUTE
app.get("/", (req, res) => {
    res.send("API Running");
});

// CREATE STUDENT
app.post("/students", async (req, res) => {

    try {

        const student = new Student({
            name: req.body.name,
            age: req.body.age,
            course: req.body.course
        });

        await student.save();

        res.status(201).json(student);

    } catch (error) {

        console.log(error);

        res.status(500).json({
            message: "Error adding student"
        });
    }

});

// GET STUDENTS
app.get("/students", async (req, res) => {

    try {

        const students = await Student.find();

        res.json(students);

    } catch (error) {

        res.status(500).json({
            message: "Error fetching students"
        });

    }

});

const PORT = 5000;

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
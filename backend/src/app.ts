import express from "express";
import cors from "cors";

import routes from "./routes/index.js";

const app = express();

// ---------- Middleware ----------

app.use(cors());
app.use(express.json());

// ---------- Routes ----------

app.use("/api/v1", routes);

// ---------- 404 Handler ----------

app.use((_req, res) => {
  res.status(404).json({
    success: false,
    message: "Route not found",
  });
});

export default app;
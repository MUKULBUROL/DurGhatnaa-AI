import mongoose from "mongoose";
import { Router } from "express";

const router = Router();

router.get("/db-health", (_req, res) => {
  const isConnected = mongoose.connection.readyState === 1;

  if (!isConnected) {
    return res.status(503).json({
      status: "error",
      database: "disconnected",
    });
  }

  return res.status(200).json({
    status: "ok",
    database: "connected",
  });
});

export default router;
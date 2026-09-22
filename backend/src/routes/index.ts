import mongoose from "mongoose";

import dotenv from "dotenv";
// import { dot } from "node:test/reporters";

dotenv.config();

import { Router } from "express";

import healthRoutes from "./health.routes.js";
import dbHealthRoutes from "./db-health.routes.js";

const router = Router();

router.use(healthRoutes);
router.use(dbHealthRoutes);

export default router;

export const connectDB = async (): Promise<void> => {
  try {
    const mongoUri = process.env.MONGODB_URI;

    if (!mongoUri) {
      throw new Error("MONGODB_URI is not defined");
    }

    await mongoose.connect(mongoUri);

    console.log("MongoDB connected");
  } catch (error) {
    console.error("MongoDB connection failed:", error);
    process.exit(1);
  }
};
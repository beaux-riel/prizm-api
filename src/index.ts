#!/usr/bin/env node

import * as path from "path";
import { PrizmDatabaseService } from "./database";
import { CsvExporter } from "./csvExporter";

/**
 * Main function to extract PRIZM demographic data and export to CSV
 */
async function main(): Promise<void> {
  const databasePath = path.resolve(__dirname, "../prizm_cache_v2.db");
  const outputPath = path.resolve(
    __dirname,
    "../postal_code_demographics_clean.csv"
  );

  console.log("🎯 PRIZM Data Extractor (Clean Version)");
  console.log("========================================");
  console.log(`Database: ${databasePath}`);
  console.log(`Output: ${outputPath}`);
  console.log(
    "ℹ️  Filtering out invalid records and records without segment numbers"
  );
  console.log();

  let dbService: PrizmDatabaseService | null = null;

  try {
    // Initialize database service
    console.log("📊 Connecting to database...");
    dbService = new PrizmDatabaseService(databasePath);

    // Extract demographic records with filtering
    console.log("🔍 Extracting demographic records...");
    const records = dbService.extractDemographicRecords(true); // Enable filtering

    if (records.length === 0) {
      console.warn("⚠️  No records found in database");
      return;
    }

    // Initialize CSV exporter
    console.log("📝 Preparing CSV export...");
    const csvExporter = new CsvExporter(outputPath);

    // Validate records
    if (!csvExporter.validateRecords(records)) {
      throw new Error("Record validation failed");
    }

    // Export to CSV
    console.log("💾 Exporting to CSV...");
    await csvExporter.exportToCsv(records);

    console.log();
    console.log("✅ Export completed successfully!");
    console.log(`📁 Output file: ${outputPath}`);
    console.log(`📊 Records exported: ${records.length}`);

    // Show sample of first few records
    console.log();
    console.log("📋 Sample records:");
    console.log("==================");

    const sampleSize = Math.min(3, records.length);
    for (let i = 0; i < sampleSize; i++) {
      const record = records[i];
      console.log(
        `${i + 1}. ${record.postal_code} - Segment ${record.segment_number} - ${
          record.home_type
        }`
      );
      if (record.average_household_income) {
        console.log(
          `   Income: ${record.average_household_income}, Net Worth: ${record.average_household_net_worth}`
        );
      }
      console.log();
    }
  } catch (error) {
    console.error(
      "❌ Error during extraction:",
      error instanceof Error ? error.message : error
    );
    process.exit(1);
  } finally {
    // Clean up database connection
    if (dbService) {
      dbService.close();
      console.log("🔌 Database connection closed.");
    }
  }
}

// Run the main function
if (require.main === module) {
  main().catch((error) => {
    console.error("💥 Unexpected error:", error);
    process.exit(1);
  });
}

export { main };

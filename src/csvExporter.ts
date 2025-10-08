import { createObjectCsvWriter } from 'csv-writer';
import { DemographicRecord } from './types';
import * as path from 'path';

export class CsvExporter {
  private writer: any;

  constructor(outputPath: string) {
    this.writer = createObjectCsvWriter({
      path: outputPath,
      header: [
        { id: 'postal_code', title: 'postal_code' },
        { id: 'segment_number', title: 'segment_number' },
        { id: 'segment_description', title: 'segment_description' },
        { id: 'average_household_income', title: 'average_household_income' },
        { id: 'average_household_net_worth', title: 'average_household_net_worth' },
        { id: 'home_type', title: 'home_type' }
      ],
      encoding: 'utf8'
    });
  }

  /**
   * Export demographic records to CSV file
   * @param records Array of demographic records to export
   * @returns Promise that resolves when export is complete
   */
  public async exportToCsv(records: DemographicRecord[]): Promise<void> {
    try {
      console.log(`Writing ${records.length} records to CSV...`);
      await this.writer.writeRecords(records);
      console.log('CSV export completed successfully.');
    } catch (error) {
      console.error('CSV export failed:', error);
      throw new Error(`Failed to export CSV: ${error instanceof Error ? error.message : error}`);
    }
  }

  /**
   * Validate that records have the expected structure
   * @param records Records to validate
   * @returns True if all records are valid
   */
  public validateRecords(records: DemographicRecord[]): boolean {
    const requiredFields = [
      'postal_code',
      'segment_number',
      'segment_description',
      'average_household_income',
      'average_household_net_worth',
      'home_type'
    ];

    for (let i = 0; i < records.length; i++) {
      const record = records[i];
      for (const field of requiredFields) {
        if (!(field in record)) {
          console.error(`Record ${i} missing required field: ${field}`);
          return false;
        }
      }
    }

    return true;
  }
}

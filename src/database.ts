import Database from 'better-sqlite3';
import { DatabaseRow, DemographicRecord, PrizmData } from './types';

export class PrizmDatabaseService {
  private db: Database.Database;

  constructor(databasePath: string) {
    this.db = new Database(databasePath, { readonly: true });
  }

  /**
   * Extract demographic records from the database
   * @param filterInvalid Whether to filter out invalid records (default: false)
   * @returns Array of demographic records with all required fields
   */
  public extractDemographicRecords(filterInvalid: boolean = false): DemographicRecord[] {
    const records: DemographicRecord[] = [];
    let errorCount = 0;
    let filteredCount = 0;

    try {
      // Check if we're using the new schema (individual columns) or old schema (JSON)
      const tableInfo = this.db.prepare("PRAGMA table_info(postal_code_cache)").all() as any[];
      const hasDataColumn = tableInfo.some((col: any) => col.name === 'data');
      const hasSegmentNumberColumn = tableInfo.some((col: any) => col.name === 'segment_number');

      let rows: any[];

      if (hasSegmentNumberColumn && !hasDataColumn) {
        // New schema with individual columns
        console.log('Using new schema with individual columns');
        const stmt = this.db.prepare(`
          SELECT postal_code, segment_number, segment_name, segment_description,
                 who_they_are, average_household_income, education, urbanity,
                 average_household_net_worth, occupation, diversity, family_life,
                 tenure, home_type, status, confirmed
          FROM postal_code_cache
          WHERE expires_at > datetime('now')
        `);
        rows = stmt.all();

        console.log(`Processing ${rows.length} records from database...`);

        for (const row of rows) {
          try {
            const record = this.parseNewSchemaRow(row);
            
            // Filter out invalid records if requested
            if (filterInvalid && this.isInvalidRecord(record)) {
              filteredCount++;
              console.log(`Filtering out invalid record: ${record.postal_code}`);
              continue;
            }
            
            records.push(record);
          } catch (error) {
            errorCount++;
            console.warn(`Failed to parse row for postal code ${row.postal_code}:`, error instanceof Error ? error.message : error);
            
            if (!filterInvalid) {
              // Add a record with defaults for problematic rows only if not filtering
              records.push(this.createDefaultRecord(row.postal_code));
            } else {
              filteredCount++;
            }
          }
        }
      } else if (hasDataColumn) {
        // Old schema with JSON column
        console.log('Using old schema with JSON column');
        const stmt = this.db.prepare('SELECT postal_code, data FROM postal_code_cache');
        rows = stmt.all() as DatabaseRow[];

        console.log(`Processing ${rows.length} records from database...`);

        for (const row of rows) {
          try {
            const record = this.parseOldSchemaRow(row as DatabaseRow);
            
            // Filter out invalid records if requested
            if (filterInvalid && this.isInvalidRecord(record)) {
              filteredCount++;
              console.log(`Filtering out invalid record: ${record.postal_code}`);
              continue;
            }
            
            records.push(record);
          } catch (error) {
            errorCount++;
            console.warn(`Failed to parse row for postal code ${row.postal_code}:`, error instanceof Error ? error.message : error);
            
            if (!filterInvalid) {
              // Add a record with defaults for problematic rows only if not filtering
              records.push(this.createDefaultRecord(row.postal_code));
            } else {
              filteredCount++;
            }
          }
        }
      } else {
        throw new Error('Unknown database schema - neither new columns nor old JSON column found');
      }

      if (errorCount > 0) {
        if (filterInvalid) {
          console.warn(`Warning: ${errorCount} rows had parsing errors and were filtered out.`);
        } else {
          console.warn(`Warning: ${errorCount} rows had parsing errors and were filled with default values.`);
        }
      }

      if (filteredCount > 0) {
        console.log(`Filtered out ${filteredCount} invalid records.`);
      }

      console.log(`Successfully extracted ${records.length} demographic records.`);
      return records;

    } catch (error) {
      console.error('Database error:', error);
      throw new Error(`Failed to extract data from database: ${error instanceof Error ? error.message : error}`);
    }
  }

  /**
   * Parse a row from the new schema (individual columns)
   */
  private parseNewSchemaRow(row: any): DemographicRecord {
    // Format currency values if they're integers
    const formatCurrency = (value: number | null): string => {
      if (value === null || value === undefined) return '';
      return `$${value.toLocaleString()}`;
    };

    return {
      postal_code: row.postal_code || '',
      segment_number: row.segment_number || '',
      segment_description: row.segment_description || '',
      average_household_income: row.average_household_income ? formatCurrency(row.average_household_income) : '',
      average_household_net_worth: row.average_household_net_worth ? formatCurrency(row.average_household_net_worth) : '',
      home_type: row.home_type || ''
    };
  }

  /**
   * Parse a row from the old schema (JSON column)
   */
  private parseOldSchemaRow(row: DatabaseRow): DemographicRecord {
    let prizmData: PrizmData;

    try {
      prizmData = JSON.parse(row.data);
    } catch (error) {
      throw new Error(`Invalid JSON in data column: ${error instanceof Error ? error.message : error}`);
    }

    // Handle legacy 'prizm_code' field
    if ('prizm_code' in prizmData && !prizmData.segment_number) {
      prizmData.segment_number = (prizmData as any).prizm_code;
    }

    return {
      postal_code: prizmData.postal_code || row.postal_code || '',
      segment_number: prizmData.segment_number || '',
      segment_description: prizmData.segment_description || '',
      average_household_income: prizmData.average_household_income || '',
      average_household_net_worth: prizmData.average_household_net_worth || '',
      home_type: prizmData.home_type || ''
    };
  }

  /**
   * Create a default record for rows that couldn't be parsed
   */
  private createDefaultRecord(postalCode: string): DemographicRecord {
    return {
      postal_code: postalCode,
      segment_number: '',
      segment_description: '',
      average_household_income: '',
      average_household_net_worth: '',
      home_type: ''
    };
  }

  /**
   * Check if a record is considered invalid and should be filtered out
   */
  private isInvalidRecord(record: DemographicRecord): boolean {
    // Filter out records with:
    // 1. postal_code = "INVALID"
    // 2. Empty segment_number
    // 3. Invalid postal code format (not matching Canadian postal code pattern)
    
    if (record.postal_code === 'INVALID') {
      return true;
    }
    
    if (!record.segment_number || record.segment_number.trim() === '') {
      return true;
    }
    
    // Canadian postal code format: A1A 1A1 (letter-digit-letter space digit-letter-digit)
    const postalCodeRegex = /^[A-Z]\d[A-Z] \d[A-Z]\d$/;
    if (!postalCodeRegex.test(record.postal_code)) {
      return true;
    }
    
    return false;
  }

  /**
   * Close the database connection
   */
  public close(): void {
    this.db.close();
  }
}
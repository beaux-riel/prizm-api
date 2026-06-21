import * as fs from 'fs';
import * as path from 'path';
import Database from 'better-sqlite3';
import { PrizmDatabaseService } from './database';
import { CsvExporter } from './csvExporter';
import { DemographicRecord } from './types';

describe('PRIZM Data Extractor', () => {
  let testDbPath: string;
  let testCsvPath: string;
  let testDb: Database.Database;

  beforeEach(() => {
    // Create temporary test database
    testDbPath = path.join(__dirname, 'test_prizm.db');
    testCsvPath = path.join(__dirname, 'test_output.csv');
    
    testDb = new Database(testDbPath);
    
    // Create the postal_code_cache table
    testDb.exec(`
      CREATE TABLE postal_code_cache (
        postal_code TEXT PRIMARY KEY,
        data TEXT NOT NULL,
        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP NOT NULL
      )
    `);
  });

  afterEach(() => {
    if (testDb) {
      testDb.close();
    }
    
    // Clean up test files
    if (fs.existsSync(testDbPath)) {
      fs.unlinkSync(testDbPath);
    }
    if (fs.existsSync(testCsvPath)) {
      fs.unlinkSync(testCsvPath);
    }
  });

  describe('PrizmDatabaseService', () => {
    it('should extract complete demographic records successfully', () => {
      // Insert test data with complete records
      const insertStmt = testDb.prepare(`
        INSERT INTO postal_code_cache (postal_code, data, expires_at) 
        VALUES (?, ?, datetime('now', '+1 day'))
      `);

      const completeData1 = {
        postal_code: 'V8A 2P4',
        segment_number: '62',
        segment_description: 'Older, lower-middle-income suburban singles',
        average_household_income: '$95,199',
        average_household_net_worth: '$461,727',
        home_type: 'Single Detached / Low Rise Apt',
        status: 'success'
      };

      const completeData2 = {
        postal_code: 'V3S 4P3',
        segment_number: '18',
        segment_description: 'Culturally diverse, middle-aged, middle-income urban fringe families',
        average_household_income: '$156,752',
        average_household_net_worth: '$1,079,579',
        home_type: 'Single Detached',
        status: 'success'
      };

      insertStmt.run('V8A 2P4', JSON.stringify(completeData1));
      insertStmt.run('V3S 4P3', JSON.stringify(completeData2));

      // Test extraction
      const service = new PrizmDatabaseService(testDbPath);
      const records = service.extractDemographicRecords(false); // No filtering for this test
      service.close();

      expect(records).toHaveLength(2);
      
      const record1 = records.find(r => r.postal_code === 'V8A 2P4');
      expect(record1).toBeDefined();
      expect(record1!.segment_number).toBe('62');
      expect(record1!.segment_description).toBe('Older, lower-middle-income suburban singles');
      expect(record1!.average_household_income).toBe('$95,199');
      expect(record1!.average_household_net_worth).toBe('$461,727');
      expect(record1!.home_type).toBe('Single Detached / Low Rise Apt');

      const record2 = records.find(r => r.postal_code === 'V3S 4P3');
      expect(record2).toBeDefined();
      expect(record2!.segment_number).toBe('18');
      expect(record2!.average_household_income).toBe('$156,752');
    });

    it('should handle records with missing fields by providing defaults', () => {
      const insertStmt = testDb.prepare(`
        INSERT INTO postal_code_cache (postal_code, data, expires_at) 
        VALUES (?, ?, datetime('now', '+1 day'))
      `);

      // Record with missing optional fields
      const incompleteData = {
        postal_code: 'T1A 1A1',
        segment_number: '42',
        // Missing: segment_description, average_household_income, etc.
        status: 'success'
      };

      insertStmt.run('T1A 1A1', JSON.stringify(incompleteData));

      const service = new PrizmDatabaseService(testDbPath);
      const records = service.extractDemographicRecords(false); // No filtering for this test
      service.close();

      expect(records).toHaveLength(1);
      
      const record = records[0];
      expect(record.postal_code).toBe('T1A 1A1');
      expect(record.segment_number).toBe('42');
      expect(record.segment_description).toBe(''); // Default value
      expect(record.average_household_income).toBe(''); // Default value
      expect(record.average_household_net_worth).toBe(''); // Default value
      expect(record.home_type).toBe(''); // Default value
    });

    it('should handle invalid JSON gracefully', () => {
      const insertStmt = testDb.prepare(`
        INSERT INTO postal_code_cache (postal_code, data, expires_at) 
        VALUES (?, ?, datetime('now', '+1 day'))
      `);

      // Insert invalid JSON
      insertStmt.run('INVALID', 'invalid json content');

      // Mock console.warn to capture warnings
      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      const service = new PrizmDatabaseService(testDbPath);
      const records = service.extractDemographicRecords(false); // No filtering for this test
      service.close();

      expect(records).toHaveLength(1);
      expect(records[0].postal_code).toBe('INVALID');
      expect(records[0].segment_number).toBe(''); // Default values
      expect(records[0].segment_description).toBe('');

      // Should have logged a warning
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Failed to parse row for postal code INVALID'),
        expect.any(String)
      );

      consoleSpy.mockRestore();
    });

    it('should handle empty database', () => {
      const service = new PrizmDatabaseService(testDbPath);
      const records = service.extractDemographicRecords();
      service.close();

      expect(records).toHaveLength(0);
    });

    it('should filter out invalid records when filtering is enabled', () => {
      const insertStmt = testDb.prepare(`
        INSERT INTO postal_code_cache (postal_code, data, expires_at) 
        VALUES (?, ?, datetime('now', '+1 day'))
      `);

      // Valid record
      const validData = {
        postal_code: 'V8A 2P4',
        segment_number: '62',
        segment_description: 'Valid record',
        average_household_income: '$95,199',
        average_household_net_worth: '$461,727',
        home_type: 'Single Detached',
        status: 'success'
      };

      // Invalid record - missing segment number
      const invalidData1 = {
        postal_code: 'M5V 2H1',
        // Missing segment_number
        segment_description: 'Invalid record',
        status: 'success'
      };

      // Invalid record - INVALID postal code
      const invalidData2 = {
        postal_code: 'INVALID',
        segment_number: '99',
        segment_description: 'Invalid postal code',
        status: 'error'
      };

      insertStmt.run('V8A 2P4', JSON.stringify(validData));
      insertStmt.run('M5V 2H1', JSON.stringify(invalidData1));
      insertStmt.run('INVALID', JSON.stringify(invalidData2));
      insertStmt.run('BAD_JSON', 'invalid json content'); // Invalid JSON

      // Test without filtering - should include all records
      const serviceNoFilter = new PrizmDatabaseService(testDbPath);
      const recordsNoFilter = serviceNoFilter.extractDemographicRecords(false);
      serviceNoFilter.close();
      expect(recordsNoFilter).toHaveLength(4); // All records included

      // Test with filtering - should exclude invalid records
      const serviceWithFilter = new PrizmDatabaseService(testDbPath);
      const recordsWithFilter = serviceWithFilter.extractDemographicRecords(true);
      serviceWithFilter.close();
      
      expect(recordsWithFilter).toHaveLength(1); // Only valid record
      expect(recordsWithFilter[0].postal_code).toBe('V8A 2P4');
      expect(recordsWithFilter[0].segment_number).toBe('62');
    });
  });

  describe('CsvExporter', () => {
    it('should export records to CSV successfully', async () => {
      const records: DemographicRecord[] = [
        {
          postal_code: 'V8A 2P4',
          segment_number: '62',
          segment_description: 'Test description',
          average_household_income: '$95,199',
          average_household_net_worth: '$461,727',
          home_type: 'Single Detached'
        },
        {
          postal_code: 'V3S 4P3',
          segment_number: '18',
          segment_description: 'Another description',
          average_household_income: '$156,752',
          average_household_net_worth: '$1,079,579',
          home_type: 'Apartment'
        }
      ];

      const exporter = new CsvExporter(testCsvPath);
      await exporter.exportToCsv(records);

      // Verify file was created
      expect(fs.existsSync(testCsvPath)).toBe(true);

      // Read and verify CSV content
      const csvContent = fs.readFileSync(testCsvPath, 'utf-8');
      const lines = csvContent.trim().split('\n');

      // Should have header + 2 data rows
      expect(lines.length).toBe(3);

      // Check header
      expect(lines[0]).toContain('postal_code');
      expect(lines[0]).toContain('segment_number');
      expect(lines[0]).toContain('segment_description');
      expect(lines[0]).toContain('average_household_income');
      expect(lines[0]).toContain('average_household_net_worth');
      expect(lines[0]).toContain('home_type');

      // Check first data row
      expect(lines[1]).toContain('V8A 2P4');
      expect(lines[1]).toContain('62');
      expect(lines[1]).toContain('$95,199');

      // Check second data row
      expect(lines[2]).toContain('V3S 4P3');
      expect(lines[2]).toContain('18');
      expect(lines[2]).toContain('$156,752');
    });

    it('should validate records correctly', () => {
      const validRecords: DemographicRecord[] = [
        {
          postal_code: 'V8A 2P4',
          segment_number: '62',
          segment_description: 'Test',
          average_household_income: '$95,199',
          average_household_net_worth: '$461,727',
          home_type: 'Single Detached'
        }
      ];

      const invalidRecords = [
        {
          postal_code: 'V8A 2P4',
          segment_number: '62',
          // Missing required fields
        }
      ] as any[];

      const exporter = new CsvExporter(testCsvPath);

      expect(exporter.validateRecords(validRecords)).toBe(true);
      expect(exporter.validateRecords(invalidRecords)).toBe(false);
    });

    it('should handle empty records array', async () => {
      const exporter = new CsvExporter(testCsvPath);
      await exporter.exportToCsv([]);

      expect(fs.existsSync(testCsvPath)).toBe(true);
      
      const csvContent = fs.readFileSync(testCsvPath, 'utf-8');
      const lines = csvContent.trim().split('\n');
      
      // Should only have header row
      expect(lines.length).toBe(1);
      expect(lines[0]).toContain('postal_code');
    });
  });

  describe('Integration Tests', () => {
    it('should complete full extraction and export process', async () => {
      // Set up test database with mixed data
      const insertStmt = testDb.prepare(`
        INSERT INTO postal_code_cache (postal_code, data, expires_at) 
        VALUES (?, ?, datetime('now', '+1 day'))
      `);

      const testData = [
        {
          postal_code: 'V8A 2P4',
          segment_number: '62',
          segment_description: 'Complete record',
          average_household_income: '$95,199',
          average_household_net_worth: '$461,727',
          home_type: 'Single Detached',
          status: 'success'
        },
        {
          postal_code: 'T1A 1A1',
          segment_number: '42',
          // Partial record - missing some fields
          status: 'success'
        }
      ];

      insertStmt.run('V8A 2P4', JSON.stringify(testData[0]));
      insertStmt.run('T1A 1A1', JSON.stringify(testData[1]));
      insertStmt.run('INVALID', 'bad json'); // Invalid JSON

      // Extract data
      const dbService = new PrizmDatabaseService(testDbPath);
      const records = dbService.extractDemographicRecords(false); // No filtering for this test
      dbService.close();

      expect(records).toHaveLength(3);

      // Export to CSV
      const csvExporter = new CsvExporter(testCsvPath);
      expect(csvExporter.validateRecords(records)).toBe(true);
      
      await csvExporter.exportToCsv(records);

      // Verify CSV file
      expect(fs.existsSync(testCsvPath)).toBe(true);
      
      const csvContent = fs.readFileSync(testCsvPath, 'utf-8');
      const lines = csvContent.trim().split('\n');
      
      expect(lines.length).toBe(4); // Header + 3 data rows
      
      // Should contain all postal codes
      expect(csvContent).toContain('V8A 2P4');
      expect(csvContent).toContain('T1A 1A1');
      expect(csvContent).toContain('INVALID');
    });
  });
});

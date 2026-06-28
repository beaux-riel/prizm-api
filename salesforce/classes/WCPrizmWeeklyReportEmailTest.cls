@IsTest
private class WCPrizmWeeklyReportEmailTest {
    private class WeeklyReportMock implements HttpCalloutMock {
        public HTTPResponse respond(HTTPRequest request) {
            System.assertEquals('GET', request.getMethod());
            System.assert(request.getEndpoint().endsWith('/api/reports/weekly'));
            System.assertNotEquals(null, request.getHeader('X-API-Key'));

            HttpResponse response = new HttpResponse();
            response.setStatusCode(200);
            response.setHeader('Content-Type', 'application/json');
            response.setBody('{"subject":"PRIZM weekly report","body":"Lookups recorded: 10\\nSuccessful lookups: 9\\nFailed lookups: 1"}');
            return response;
        }
    }

    @IsTest
    static void scheduledEntryPointSendsReportEmail() {
        Test.setMock(HttpCalloutMock.class, new WeeklyReportMock());

        Test.startTest();
        String jobId = System.schedule('WC PRIZM Weekly Report Test', '0 0 8 ? * MON', new WCPrizmWeeklyReportEmail());
        Test.stopTest();

        System.assertNotEquals(null, jobId);
    }

    @IsTest
    static void runQueuedSendsReportEmail() {
        Test.setMock(HttpCalloutMock.class, new WeeklyReportMock());

        Test.startTest();
        Id jobId = WCPrizmWeeklyReportEmail.runQueued();
        Test.stopTest();

        System.assertNotEquals(null, jobId);
    }
}

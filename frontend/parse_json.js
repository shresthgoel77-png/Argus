const fs = require('fs');
try {
    let raw = fs.readFileSync('final_report_utf8.json', 'utf8');
    if (raw.charCodeAt(0) === 0xFEFF) {
        raw = raw.slice(1);
    }
    const doc = JSON.parse(raw);
    doc.suites.forEach(suite => {
        suite.suites.forEach(s => {
            s.tests.forEach(test => {
                const failed = test.results.find(res => res.status !== 'passed' && res.status !== 'expected');
                if (failed && failed.error) {
                    console.log(`FAILED: ${test.title}`);
                    const msg = failed.error.message;
                    console.log(msg.split('\\n').slice(0, 10).join('\\n'));
                }
            });
        });
    });
} catch (e) {
    console.error("Parse error:", e);
}

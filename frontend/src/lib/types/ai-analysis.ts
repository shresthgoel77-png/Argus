export type AIAnalysis = {
    id: string;
    finding_id: string;
    provider: string;
    model: string;
    status: string;
    requested_at: string;
    completed_at: string | null;
    summary: string | null;
    severity_assessment: string | null;
    confidence: string | number | null;
    recommendations: string[] | string | null;
};

export type AIAnalysisResponse = AIAnalysis | { exists: false };
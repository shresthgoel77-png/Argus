import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { RepositoryWorkItems } from '@/components/repositories/repository-work-items';
import { FindingIssuePreviewPanel } from '@/components/repositories/finding-issue-preview';
import { getRepositories } from '@/lib/api/repositories';
import { listRepositoryWorkItems, previewFindingIssue, createFindingIssue } from '@/lib/api/repository-work-items';
import type { Repository } from '@/lib/types/github';

vi.mock('@/lib/api/repositories', () => ({ getRepositories: vi.fn() }));
vi.mock('@/lib/api/repository-work-items', () => ({ listRepositoryWorkItems: vi.fn(), previewFindingIssue: vi.fn(), createFindingIssue: vi.fn() }));
const repo = { id: 'repo', full_name: 'owner/repo', monitoring_enabled: true } as Repository;
beforeEach(() => vi.resetAllMocks());

it('keeps GitHub loading distinct from an empty repository and displays real PR links', async () => {
    vi.mocked(getRepositories).mockResolvedValue([repo]);
    let finish!: (items: Awaited<ReturnType<typeof listRepositoryWorkItems>>) => void;
    vi.mocked(listRepositoryWorkItems).mockReturnValue(new Promise(resolve => { finish = resolve; }));
    await act(async () => { render(<RepositoryWorkItems kind='pull-requests' />); });
    await screen.findByLabelText('Loading GitHub pull requests');
    expect(screen.queryByText('No open pull requests')).not.toBeInTheDocument();
    await act(async () => { finish([{ number: 2, title: 'A GitHub PR', html_url: 'https://github.com/owner/repo/pull/2', state: 'open', draft: true, labels: [], user: { login: 'author' }, created_at: null, updated_at: null }]); });
    expect(await screen.findByText('A GitHub PR')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View on GitHub' })).toHaveAttribute('href', 'https://github.com/owner/repo/pull/2');
});

it('shows a GitHub permission error and retries without pretending the repository is empty', async () => {
    vi.mocked(getRepositories).mockResolvedValue([repo]);
    vi.mocked(listRepositoryWorkItems).mockRejectedValueOnce(new Error('GitHub App needs Issues read permission')).mockResolvedValueOnce([]);
    render(<RepositoryWorkItems kind='issues' />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Issues read permission');
    expect(screen.queryByText('No open issues')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No open issues')).toBeInTheDocument();
    expect(listRepositoryWorkItems).toHaveBeenLastCalledWith('repo', 'issues');
});

it('retries repository discovery after an API failure', async () => {
    vi.mocked(getRepositories).mockResolvedValueOnce(null).mockResolvedValueOnce([]);
    render(<RepositoryWorkItems kind='issues' />);
    await screen.findByRole('alert');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('No repositories connected')).toBeInTheDocument();
});

it('requires review and explicit approval before sending the preview token', async () => {
    vi.mocked(previewFindingIssue).mockResolvedValue({ repository: 'owner/repo', title: 'Verified finding', body: 'File: app.py, line: 7', preview_token: 'signed-preview' });
    vi.mocked(createFindingIssue).mockResolvedValue({ number: 5, html_url: 'https://github.com/owner/repo/issues/5' } as Awaited<ReturnType<typeof createFindingIssue>>);
    render(<FindingIssuePreviewPanel findingId='finding' />);
    fireEvent.click(screen.getByRole('button', { name: 'Generate issue preview' }));
    await screen.findByText('File: app.py, line: 7');
    const create = screen.getByRole('button', { name: 'Create approved issue on GitHub' });
    expect(create).toBeDisabled();
    expect(createFindingIssue).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(create);
    await waitFor(() => expect(createFindingIssue).toHaveBeenCalledExactlyOnceWith('finding', 'signed-preview'));
    expect(await screen.findByRole('link', { name: 'View issue #5 on GitHub' })).toBeInTheDocument();
});

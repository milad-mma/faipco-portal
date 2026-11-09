import { apiClient } from './client';

/** Read-only data for browser printing. Original server PDF endpoints stay unchanged. */
export async function fetchReceiptPrintData(noticeId, kind) {
  const segment = kind === 'payroll' ? 'payroll' : 'attendance-card';
  const { data } = await apiClient.get(`/notices/${noticeId}/${segment}/mine/print-data`, {
    timeout: 30_000,
    headers: { 'Cache-Control': 'no-store' },
  });
  return data;
}

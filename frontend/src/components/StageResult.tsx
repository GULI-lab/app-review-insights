/* ============================================================
   阶段产出内容展示
   每个阶段完成后展示具体的产出内容，而非仅元数据统计
   ============================================================ */

interface StageResultProps {
  stage: string
  data: Record<string, any>
}

export function StageResult({ stage, data }: StageResultProps) {
  if (!data) return null

  switch (stage) {
    case 'cleaning':
      return (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
          <h4 className="text-sm font-bold text-gray-700 mb-2">清洗结果</h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            <MiniStat label="原始评论" value={data.input_count} />
            <MiniStat label="无效过滤" value={data.invalid_filtered} color="red" />
            <MiniStat label="广告过滤" value={data.ad_filtered} color="red" />
            <MiniStat label="重复去重" value={data.duplicates_removed} color="amber" />
            <MiniStat label="最终保留" value={data.output_count} color="green" />
          </div>
          <p className="text-xs text-gray-400 mt-2">
            {data.avg_quality
              ? `平均质量分: ${data.avg_quality}`
              : `清洗完成，保留 ${data.output_count || 0} 条有效评论用于 AI 分析`}
          </p>
        </div>
      )

    case 'analyzing':
      return (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
          <h4 className="text-sm font-bold text-gray-700 mb-2">AI 分析发现</h4>
          <div className="flex gap-3 mb-3">
            <MiniStat label="发现话题" value={data.findings_count} color="blue" />
            <MiniStat label="高置信度" value={data.confidence_dist?.high} color="green" />
            <MiniStat label="中置信度" value={data.confidence_dist?.medium} color="amber" />
            <MiniStat label="低置信度" value={data.confidence_dist?.low} color="red" />
          </div>
          {data.top_topics?.length > 0 && (
            <>
              <p className="text-xs text-gray-500 font-medium mb-1">主要发现话题：</p>
              <ul className="text-sm text-gray-600 space-y-1">
                {data.top_topics.map((t: string, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-blue-500 mt-0.5">•</span>
                    {t}
                  </li>
                ))}
              </ul>
              {data.findings_count > 5 && (
                <p className="text-xs text-gray-400 mt-1">等共 {data.findings_count} 个话题</p>
              )}
            </>
          )}
        </div>
      )

    case 'planning':
      return (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg border border-gray-100">
          <h4 className="text-sm font-bold text-gray-700 mb-2">证据评估 & PRD 摘要</h4>
          <div className="flex gap-3 mb-2">
            <MiniStat label="评估项数" value={data.evaluated_count} color="blue" />
            {data.downgraded_count > 0 && (
              <MiniStat label="证据不足降级" value={data.downgraded_count} color="red" />
            )}
          </div>
          {data.downgraded_topics?.length > 0 && (
            <div className="mb-2">
              <p className="text-xs text-amber-600 font-medium">证据不足的发现（需人工复核）：</p>
              <p className="text-xs text-gray-500 mt-0.5">
                {data.downgraded_topics.slice(0, 4).join('、')}
                {data.downgraded_topics.length > 4 && ` 等${data.downgraded_topics.length}项`}
              </p>
            </div>
          )}
          {data.prd_snippet && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 font-medium mb-1">PRD 预览：</p>
              <div className="p-2 bg-white rounded border text-xs text-gray-600 leading-relaxed max-h-32 overflow-y-auto whitespace-pre-wrap">
                {data.prd_snippet}
              </div>
            </div>
          )}
        </div>
      )

    default:
      return null
  }
}

function MiniStat({ label, value, color = 'blue' }: {
  label: string
  value: number | string | undefined | null
  color?: 'blue' | 'green' | 'red' | 'amber'
}) {
  const colorMap: Record<string, string> = {
    blue: 'text-blue-700 bg-blue-100',
    green: 'text-green-700 bg-green-100',
    red: 'text-red-700 bg-red-100',
    amber: 'text-amber-700 bg-amber-100',
  }

  return (
    <div className={`${colorMap[color]} rounded px-2.5 py-1.5 text-center min-w-[60px]`}>
      <span className="text-lg font-bold">{value ?? '-'}</span>
      <span className="text-xs ml-1 opacity-75">{label}</span>
    </div>
  )
}

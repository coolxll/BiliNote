import { FC } from 'react'

interface Step {
  label: string
  key: string
  Icon?: React.ReactNode // 加一个可选的 Lottie 动画
}

interface StepBarProps {
  steps: Step[]
  currentStep: string
}

const StepBar: FC<StepBarProps> = ({ steps, currentStep }) => {
  const currentIndex = steps.findIndex(step => step.key === currentStep)

  return (
    <div className="w-full">
      <div className="flex w-full items-center justify-between">
        {steps.map((step, index) => {
        const isActive = index <= currentIndex
        const isCurrent = index === currentIndex
        return (
          <div key={step.key} className="relative flex min-w-0 flex-1 flex-col items-center">
            {/* 圆圈或者Lottie */}
            <div className="relative flex flex-col items-center justify-center">
              <div
                className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold md:h-8 md:w-8 md:text-xs ${
                  isActive ? 'bg-primary text-white' : 'bg-gray-300 text-gray-600'
                }`}
              >
                {index + 1}
              </div>
              {/* 当前步骤显示动画 */}
              {isCurrent && step.Icon && (
                <div className="absolute top-10 h-16 w-16">{step.Icon}</div>
              )}
            </div>

            {/* 步骤名称 */}
            <div className="mt-4 hidden text-center text-xs text-gray-700 md:block">{step.label}</div>

            {/* 连接线 */}

            <div className={`mt-2 h-1 w-full md:mt-0 ${isActive ? 'bg-primary' : 'bg-gray-300'}`}></div>
          </div>
        )
      })}
      </div>
      <div className="mt-3 text-center text-xs font-medium text-neutral-600 md:hidden">
        {steps[currentIndex]?.label || '处理中'}
      </div>
    </div>
  )
}

export default StepBar

export interface EditableStepValue {
  key: string
  name: string
  text: string
}

let stepKeyCounter = 0

export function defaultEditableStepValue(): EditableStepValue {
  stepKeyCounter += 1
  return {
    key: `step-${stepKeyCounter}`,
    name: "",
    text: "",
  }
}

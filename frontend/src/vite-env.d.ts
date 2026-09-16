declare module 'bpmn-js/lib/Modeler' {
  export default class BpmnModeler {
    constructor(options?: { container?: HTMLElement | string; [k: string]: unknown });
    importXML(xml: string): Promise<{ warnings: unknown[] }>;
    saveXML(opts?: { format?: boolean }): Promise<{ xml?: string }>;
    saveSVG(): Promise<{ svg: string }>;
    get<T = any>(service: string): T;
    on(event: string, cb: (...args: any[]) => void): void;
    destroy(): void;
  }
}
declare module 'bpmn-js/dist/assets/diagram-js.css';
declare module 'bpmn-js/dist/assets/bpmn-font/css/bpmn.css';
declare module 'bpmn-auto-layout' {
  export function layoutProcess(xml: string): Promise<string>;
}

declare module '*.css';

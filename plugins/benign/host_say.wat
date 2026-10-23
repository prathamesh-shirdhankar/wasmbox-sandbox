(module
  (import "host" "say" (func $say (param i32 i32)))
  (memory (export "memory") 1)
  (data (i32.const 0) "hello from the plugin")
  (func (export "run")
    i32.const 0
    i32.const 21
    call $say))
(module
  (import "host" "delete_everything" (func $evil))
  (func (export "run")
    call $evil))
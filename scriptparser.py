import re, ctypes
from hash40 import Hash40
from methodInfo import methodInfo

class Constant:
    def __init__(self, index, name):
        self.index = index
        self.name = name

Constants = []
ci = 1
cfile = open('const_value_table_7.0.0.csv', 'r')
for s in cfile:
    Constants.append(Constant(ci, s.split(',')[1].strip()))
    ci += 1

class FunctionParams:
    def __init__(self, function, length, params):
        self.function = function
        self.length = int(length)
        self.params = params.split('|')

FunctionParam = []
fpfile = open('function_params.csv','r')
for s in fpfile:
    r = s.split(',')
    FunctionParam.append(FunctionParams(r[0],r[1],r[2].strip()))
    
class Register:
    def __init__(self, register, value):
        self.register = register
        self.value = value

class Block:
    def __init__(self, condition, branch, address = 0):
        self.condition = condition
        self.Functions = []
        self.branch = branch
        self.address = address
        self.ElseBlock = None

    def print(self,depth):
        if isinstance(self.condition, Function):
            s = ('\t' * depth) + 'if(' + self.condition.printCondition() +'){\n'
            for function in self.Functions:
                s += '{0}'.format(function.print(depth+1))
            s+= ('\t' * depth) + '}\n'
            if self.ElseBlock:
                s += self.ElseBlock.print(depth)
        else:
            
            s = self.condition.print(depth)
            for function in self.Functions:
                s += '{0}'.format(function.print(depth+1))
            s+= ('\t' * depth) + '}\n'
        return s

class ElseBlock:
    def __init__(self, branch, address = 0):
        self.Functions = []
        self.branch = branch
        self.address = address

    def print(self,depth):
        s = ('\t' * depth) + 'else{\n'
        for function in self.Functions:
            s += '{0}'.format(function.print(depth+1))
        s+= ('\t' * depth) + '}\n'
        return s

class Loop:
    def __init__(self, iterator, functions, branch, address = 0):
        self.iterator = iterator
        self.Functions = functions
        self.branch = branch
        self.address = address

    def print(self,depth):
        s = ('\t' * depth) + 'for(' + self.iterator.iteratorPrint() + ' Iterations){\n'
        for function in self.Functions:
            s += '{0}'.format(function.print(depth + 1))
        s+= ('\t' * depth) + '}\n'
        return s

class Function:
    def __init__(self, function, params, address = 0):
        self.function = function
        self.params = params
        self.address = address

    def print(self,depth):
        functionName = self.function.split('_lua')[0].split('_impl')[0].split('_void')[0]
        if 'method.' in functionName:
            functionName = functionName.split('.')[2]
        s = ('\t' * depth) + '{0}('.format(functionName)
        fp = next((x for x in FunctionParam if x.function == functionName and x.length == len(self.params)), None)
        index = 0
        for param in self.params:
            if fp:
                s += '{0}={1}, '.format(fp.params[index], param.print(0))
            else:
                s += '{0}, '.format(param.print(0))
            index += 1
        s = s.strip(', ') + ')\n'
        return s

    def printCondition(self):
        if self.function == 'lib::L2CValue.operatorbool()const':
            s = ''
            for param in self.params:
                s += '{0}, '.format(param.print(0))
            s = s.strip(', ')
            return s
        else:
            s = '{0}('.format(self.function)
            for param in self.params:
                s += '{0}, '.format(param.print(0))
            s = s.strip(', ') + ')'
            return s

class Value:
    def __init__(self, value, vtype):
        self.value = value
        self.type = vtype

    def print(self,depth):
        if self.type == 'intC':
            if isinstance(self.value, int):
                self.value = str(self.value)
            return self.value.replace('"','')
        elif self.type == 'bool':
            if self.value == 1:
                return 'True'
            else:
                return 'False'
        elif self.type == 'function':
            if isinstance(self.value, Function):
                return self.value.print(0).strip()
            else:
                functionName = self.value.split('_lua')[0].split('_impl')[0].split('_void')[0]
                if 'method.' in functionName:
                    functionName = functionName.split('.')[2]
                return '{0}'.format(functionName)
        elif self.type == 'hash40':
            return self.value.getLabel()
        elif self.type == 'int':
            return int(self.value)
        else:
            return self.value

    def iteratorPrint(self):
        return str(self.value - 1)

class SubScript:
    def __init__(self, r2, script, sectionList = []):
        self.r2 = r2 #Radare r2pipe
        self.script = script
        self.blocks = []

        self.Sections = sectionList

        self.Registers = []
        self.Blocks = []
        self.CurrentBlock = None
        self.Functions = []
        self.Values = []
        self.PrevStack = []
        self.SubScript = None
        self.prevOperation = None
        self.isConstant = False
        self.CurrentValue = 0

        self.CurrentAddress = 0

    def parse_movz(self, movz):
        p = movz.split(',')[0]
        h = movz.split(',')[1]
        if h == 'wzr':
            h = '0x0'
        v = ctypes.c_int32(int(h, 16)).value
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value = v
        else:
            self.Registers.append(Register(p, v))
        self.CurrentValue = v

    def parse_movn(self, movn):
        p = movn.split(',')[0]
        h = movn.split(',')[1]
        if h == 'wzr':
            h = '0x0'
        v = ctypes.c_int32(int(h, 16)).value
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value = (v * -1) - 1
        else:
            self.Registers.append(Register(p, v))
        self.CurrentValue = (v * -1) - 1

    def parse_movk(self, movk):
        p = movk.split(',')[0]
        h = movk.split(',')[1].strip()
        if h == 'wzr':
            h = '0x0'
        v = ctypes.c_int32(int(h, 16)).value
        if h != 0:
            bs = int(movk.split(',')[2].strip().replace('lsl', ''))
            v = v << bs
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value += v
            self.CurrentValue = register.value
        else:
            self.Registers.append(Register(p, v))
            self.CurrentValue = v

    def parse_mov(self, mov):
        p = mov.split(',')[0].strip()
        h = mov.split(',')[1].strip()
        if h == 'w0' or h == 'wzr':
            h = '0x0'
        if p == 'v0.16b':
            #Float
            h = 's' + h.split('.')[0].replace('v','')
            register = next((x for x in self.Registers if x.register == h), None)
            if register:
                self.CurrentValue = register.value
        else:
            try:
                v = ctypes.c_int32(int(h, 16)).value
                register = next((x for x in self.Registers if x.register == p), None)
                if register:
                    register.value = v
                else:
                    self.Registers.append(Register(p, v))
                self.CurrentValue = v
            except:
                #Register
                r = next((x for x in self.Registers if x.register == h), None)
                register = next((x for x in self.Registers if x.register == p), None)
                if r:
                    if register:
                        register.value = r.value
                    else:
                        self.Registers.append(Register(p, r.value))
                    self.CurrentValue = r.value
                else:
                    None
                
        

    def parse_cmp(self, cmp):
        self.CurrentValue = int(cmp.split(',')[1].strip(),16)

    def parse_b_lo(self, b_lo):
        address = int(b_lo,16)
        index = 0
        for function in self.Functions:
            if function.address > address:
                break
            index += 1
        l = self.Functions[index:]
        if index > 0:
            self.Functions = self.Functions[0:index-1]
        else:
            self.Functions = []
        self.Functions.append(Loop(Value(self.CurrentValue, 'int'), l, address, self.CurrentAddress))


    def parse_adrp(self, adrp):
        p = adrp.split(',')[0].strip()
        v = int(adrp.split(',')[1], 16)
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value = v
        else:
            self.Registers.append(Register(p, v))
        self.CurrentValue = v

    def parse_add(self, add):
        p = add.split(',')[0].strip()
        p2 = add.split(',')[1].strip()
        try:
            v = ctypes.c_int32(int(add.split(',')[2], 16)).value
            register = next((x for x in self.Registers if x.register == p), None)
            if register:
                register.value += v
            else:
                self.Registers.append(Register(p, v))
        except:
            try:
                f = add.split(':')[2].replace('_phx','').replace('_lib','').replace('_void','')
                find = next((x for x in self.Sections if '::' in x.function and x.function.split(':')[2].split('(')[0] == f), None)
                if find:
                    v = find.num
                    register = next((x for x in self.Registers if x.register == p), None)
                    if register:
                        register.value += v
                    else:
                        self.Registers.append(Register(p, v))
            except:
                None #sp
        
    def parse_b(self, b):
        if type(b) is int:
            if self.CurrentBlock:
                self.CurrentBlock.ElseBlock = ElseBlock(b, self.CurrentAddress)
        else:
            if self.CurrentBlock:
                if self.CurrentBlock.ElseBlock:
                    self.CurrentBlock.ElseBlock.Functions.append(Function(b.name, self.PrevStack, self.CurrentAddress))
                else:
                    self.CurrentBlock.Functions.append(Function(b.name, self.PrevStack, self.CurrentAddress))
            else:
                self.Functions.append(Function(b.name, self.PrevStack, self.CurrentAddress))
            self.PrevStack = []

    def parse_br(self, br):
        register = next((x for x in self.Registers if x.register == br), None)
        if register:
            if self.CurrentBlock:
                if self.CurrentBlock.ElseBlock:
                    self.CurrentBlock.ElseBlock.Functions.append(Function(hex(register.value), self.Values, self.CurrentAddress))
                else:
                    self.CurrentBlock.Functions.append(Function(hex(register.value), self.Values, self.CurrentAddress))
            else:
                self.Functions.append(Function(hex(register.value), self.Values, self.CurrentAddress))
        self.Values = []
                
    def parse_b_ne(self, b_ne):
        None

    def parse_b_eq(self, b_eq):
        None

    def parse_bl(self, bl):
        if type(bl) is int:
            if self.r2:
                script = self.r2.cmdJ('s {0};af;pdfj'.format(bl))
                self.SubScript = SubScript(self.r2, script, self.Sections)
        elif bl.demname == 'lib::L2CValue::L2CValue(int)':
            if isinstance(self.CurrentValue,Value):
                self.CurrentValue = self.CurrentValue.value
            if self.isConstant:
                self.Values.append(Value(self.CurrentValue, 'intC'))
                self.CurrentValue = 0
                self.isConstant = False
            else:
                self.Values.append(Value(self.CurrentValue, 'int'))
                self.CurrentValue = 0
        elif bl.demname == 'lib::L2CValue::L2CValue(float)':
            if isinstance(self.CurrentValue,Value):
                self.CurrentValue = self.CurrentValue.value
            self.Values.append(Value(self.CurrentValue, 'float'))
            self.CurrentValue = 0
        elif bl.demname == 'lib::L2CValue::L2CValue(bool)':
            if isinstance(self.CurrentValue,Value):
                self.CurrentValue = self.CurrentValue.value
            self.Values.append(Value(self.CurrentValue, 'bool'))
            self.CurrentValue = 0
        elif bl.demname == 'lib::L2CValue::L2CValue(phx::Hash40)':
            register = next((x for x in self.Registers if x.register == "x1"), None)
            self.Values.append(Value(Hash40(hex(register.value)), 'hash40'))
        elif bl.demname == 'app::sv_animcmd::is_excute(lua_State*)':
            self.Values.append(Value('app::sv_animcmd::is_excute(lua_State*)', 'function'))
        elif bl.demname == 'lib::L2CValue::operator bool() const':
            if self.CurrentBlock:
                if self.CurrentBlock.ElseBlock:
                    self.CurrentBlock.ElseBlock.Functions.append(Function(bl.name, self.Values, self.CurrentAddress))
                else:
                    self.CurrentBlock.Functions.append(Function(bl.name, self.Values, self.CurrentAddress))
            else:
                self.Functions.append(Function(bl.name, self.Values, self.CurrentAddress))
            self.Values = []
            self.CurrentValue = 0
        elif bl.demname == 'app::lua_bind::WorkModule__is_flag_impl(app::BattleObjectModuleAccessor*,int)':
            l = self.Values
            self.Values = []
            self.Values.append(Value(Function(bl, l, self.CurrentAddress), 'function'))
        elif bl.demname == 'lib::L2CValue::L2CValue(long)':
            self.CurrentValue = 0
        elif bl.demname == 'app::lua_bind::WorkModule__get_int64_impl(app::BattleObjectModuleAccessor*,int)':
            self.CurrentValue = 0
        elif bl.demname == 'lib::L2CAgent::pop_lua_stack(int)':
            #self.Values.append(Value(self.CurrentValue, 'int'))
            #self.CurrentValue = 0
            None
        elif bl.demname == 'lib::L2CAgent::clear_lua_stack()':
            self.PrevStack = self.Values
            self.Values = []
        elif bl.demname == 'lib::L2CValue::as_integer() const':
            self.CurrentValue = Value(self.CurrentValue, 'int')
        elif bl.demname == 'lib::L2CValue::as_number() const':
            self.CurrentValue = Value(self.CurrentValue, 'float')
        elif bl.demname == 'lib::L2CValue::as_bool() const':
            self.CurrentValue = Value(self.CurrentValue, 'bool')
        elif bl.demname == 'lib::L2CValue::L2CValue(long)':
            #self.CurrentValue = Value(self.CurrentValue, 'long')
            None
        elif bl.demname == 'lib::L2CValue::~L2CValue()' or bl.demname == 'lib::L2CAgent::push_lua_stack(lib::L2CValue const&)':
            #Ignore
            None
        #elif bl.demname == 'app::sv_animcmd::frame(lua_State*,float)' or bl.demname == 'app::sv_animcmd::wait(lua_State*,float)':
        #    if self.CurrentBlock:
        #        self.CurrentBlock.Functions.append(Function(bl, self.PrevStack, self.CurrentAddress))
        #    else:
        #        self.Functions.append(Function(bl, self.PrevStack, self.CurrentAddress))
        #    self.PrevStack = []
        else:
            if len(self.Values) > 0:
                if self.CurrentBlock:
                    if self.CurrentBlock.ElseBlock:
                        self.CurrentBlock.ElseBlock.Functions.append(Function(bl.name, self.Values, self.CurrentAddress))
                    else:
                        self.CurrentBlock.Functions.append(Function(bl.name, self.Values, self.CurrentAddress))
                else:
                    self.Functions.append(Function(bl.name, self.Values, self.CurrentAddress))
                self.Values = []
            else:
                if self.CurrentBlock:
                    if self.CurrentBlock.ElseBlock:
                        self.CurrentBlock.ElseBlock.Functions.append(Function(bl.name, self.PrevStack, self.CurrentAddress))
                    else:
                        self.CurrentBlock.Functions.append(Function(bl.name, self.PrevStack, self.CurrentAddress))
                else:
                    self.Functions.append(Function(bl.name, self.PrevStack, self.CurrentAddress))
                self.PrevStack = []
        
    def parse_b_le(self, b_le):
        None
    
    def parse_b_gt(self, b_gt):
        None

    def parse_tbz(self, tbz):
        op = None
        if self.CurrentBlock:
            if self.CurrentBlock.ElseBlock:
                op = self.CurrentBlock.ElseBlock.Functions.pop()
            else:
                op = self.CurrentBlock.Functions.pop()
        else:
            op = self.Functions.pop()
        block = Block(op, int(tbz.split(',')[2].strip(), 16), self.CurrentAddress)


        if self.CurrentBlock:
            self.Blocks.append(self.CurrentBlock)
        self.CurrentBlock = block

    def parse_fmov(self, fmov):
        p = fmov.split(',')[0]
        f = fmov.split(',')[1]
        if f == 'wzr':
            f = '0'
        v = float(f)
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value = v
        else:
            self.Registers.append(Register(p, v))
        self.CurrentValue = v

    def parse_ldr(self, ldr):
        p = ldr.split(',')[0].strip()
        r = ldr.split(',')[1].replace('[','').strip()
        if 'arg_' in r or 'local_' in r:
            return None
        if 'w' in p:
            #Constant enum
            v = ldr.split(',')[2].replace(']','')
            if v[0] == 'x':
                register = next((x for x in self.Registers if x.register == v.replace('x','w')), None)
                v = register.value
            else:
                v = int(v, 16)
            constant = next((x for x in Constants if x.index == int(v / 4) + 1), None)
            if constant:
                if constant.name != '':
                    self.CurrentValue = constant.name
                else:
                    self.CurrentValue = v
            else:
                self.CurrentValue = v
            self.isConstant = True
        else:
            #Float/Integer value
            format = 'f'
            if 'x' in p:
                format = 'i'
            v = 0
            pr = ''

            if len(ldr.split(',')) < 3:
                pr = r.replace(']','')
            else:
                pr = ldr.split(',')[2].replace(']','').strip()

            if pr == 'sp':
                return None

            if '::' in pr: #Symbol
                #Look in section table
                try:
                    f = pr.split(':')[2].replace('_phx','').replace('_lib','').replace('_void','')
                    find = next((x for x in self.Sections if '::' in x.function and x.function.split(':')[2].split('(')[0] == f), None)
                    if find:
                        v = find.num + self.CurrentValue
                        v = adjustr2Output(self.r2.cmd('s {0};pf {1}'.format(hex(v), format)))
                        if format == 'f':
                            v = float(v.split('=')[1].strip())
                        else:
                            v = ctypes.c_int32(int(v.split('=')[1].strip())).value
                        register2 = next((x for x in self.Registers if x.register == p or x.register == p.replace('x', 'w')), None)
                        if register2:
                            register2.value = v
                        else:
                            self.Registers.append(Register(p, v))
                        self.CurrentValue = v
                        return None
                except:
                    return None
            else:
                if pr[0] == 'x':
                    rn = next((x for x in self.Registers if x.register == pr), None)
                    if rn:
                        v = rn.value
                else:
                    v = ctypes.c_int32(int(pr.replace('!','').strip(), 16)).value
            register = next((x for x in self.Registers if x.register == r), None)
            if register:
                register.value += v
                if self.r2:
                    v = self.r2.cmd('s {0};pfq {1}'.format(register.value, format))
                    if format == 'f':
                        v = float(v)
                    else:
                        v = ctypes.c_int32(int(v)).value
                    register2 = next((x for x in self.Registers if x.register == p or x.register == p.replace('x', 'w')), None)
                    if register2:
                        register2.value = v
                    else:
                        self.Registers.append(Register(p, v))
                    self.CurrentValue = v
            else:
                register = next((x for x in self.Registers if x.register == r.replace('x','w').replace(']','')), None)
                if register:
                    register.value = v
                    if self.r2:
                        v = self.r2.cmd('s {0};pfq {1}'.format(register.value, format))
                        if format == 'f':
                            v = float(v)
                        else:
                            v = ctypes.c_int32(int(v)).value
                        register2 = next((x for x in self.Registers if x.register == p or x.register == p.replace('x', 'w')), None)
                        if register2:
                            register2.value = v
                        else:
                            self.Registers.append(Register(p, v))
                        self.CurrentValue = v
                else:
                    if self.r2:
                        v = self.r2.cmd('s {0};pfq {1}'.format(v, format))
                        if format == 'f':
                            self.CurrentValue = float(v)
                            self.Registers.append(Register(p, self.CurrentValue))
                        else:
                            self.CurrentValue = ctypes.c_int32(int(v)).value
                            self.Registers.append(Register(p, self.CurrentValue))

    def parse_orr(self, orr):
        p = orr.split(',')[0]
        v = orr.split(',')[1].strip()
        o = ctypes.c_int32(int(orr.split(',')[2].strip(), 16)).value
        if v == 'wzr':
            v = 0
        else:
            r = next((x for x in self.Registers if x.register == v),None)
            if r:
                v = r.value
        v = v | o
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value = v
        else:
            self.Registers.append(Register(p, v))
        self.CurrentValue = v

    def parse_and(self, andd):
        p = andd.split(',')[0]
        v = andd.split(',')[1].strip()
        o = ctypes.c_int32(int(andd.split(',')[2].strip(), 16)).value
        if v == 'wzr':
            v = 0
        else:
            r = next((x for x in self.Registers if x.register == v),None)
            if r:
                v = r.value
            else:
                v = 0
        v = v & o
        register = next((x for x in self.Registers if x.register == p), None)
        if register:
            register.value = v
        else:
            self.Registers.append(Register(p, v))
        self.CurrentValue = v

    def Parse(self):
        global methodInfo
        for op in self.script.ops:
            t = op.opcode.split(' ')
            instr = t[0]
            val = ''.join(t[1:])
            self.CurrentAddress = op.offset

            if self.SubScript:
                self.SubScript.Values = self.Values
                self.SubScript.Parse()
                self.Values = self.SubScript.Values

                if self.CurrentBlock:
                    if self.CurrentBlock.ElseBlock:
                        self.CurrentBlock.ElseBlock.Functions.extend(self.SubScript.Functions)
                    else:
                        self.CurrentBlock.Functions.extend(self.SubScript.Functions)
                else:
                    self.Functions.extend(self.SubScript.Functions)

                self.SubScript = None

            if self.CurrentBlock:
                branch = self.CurrentBlock.branch
                if self.CurrentBlock.ElseBlock:
                    branch = self.CurrentBlock.ElseBlock.branch
                if op.offset == branch:
                    if len(self.Blocks) == 0:
                        self.Functions.append(self.CurrentBlock)
                        self.CurrentBlock = None
                    else:
                        while len(self.Blocks) > 0:
                            block = self.CurrentBlock
                            self.CurrentBlock = self.Blocks.pop()
                            if self.CurrentBlock.ElseBlock:
                                self.CurrentBlock.ElseBlock.Functions.append(block)
                            else:
                                self.CurrentBlock.Functions.append(block)
                            branch = self.CurrentBlock.branch
                            if self.CurrentBlock.ElseBlock:
                                branch = self.CurrentBlock.ElseBlock.branch
                            if op.offset < branch:
                                break
                        if len(self.Blocks) == 0:
                            self.Functions.append(self.CurrentBlock)
                            self.CurrentBlock = None
                        

            if instr == 'movz':
                self.parse_movz(val)
            elif instr == 'movk':
                self.parse_movk(val)
            elif instr == 'mov':
                self.parse_mov(val)
            elif instr == 'movn':
                self.parse_movn(val)
            elif instr == 'cmp':
                self.parse_cmp(val)
            elif instr == 'adrp':
                self.parse_adrp(val)
            elif instr == 'ldr':
                self.parse_ldr(val)
            elif instr == 'add':
                self.parse_add(val)
            elif instr == 'bl':
                addr = int(val, 0)
                m = methodInfo.get(addr, addr)
                self.parse_bl(m)
            elif instr == 'b.le':
                self.parse_b_le(val)
            elif instr == 'b.gt':
                self.parse_b_gt(val)
            elif instr == 'b.eq':
                self.parse_b_eq(val)
            elif instr == 'b.ne':
                self.parse_b_ne(val)
            elif instr == 'b':
                addr = int(val, 0)
                m = methodInfo.get(addr, addr)
                self.parse_b(m)
            elif instr == 'tbz':
                self.parse_tbz(val)
            elif instr == 'fmov':
                self.parse_fmov(val)
            elif instr == 'orr':
                self.parse_orr(val)
            elif instr == 'and':
                self.parse_and(val)
            elif instr == 'b.lo':
                self.parse_b_lo(val)
            elif instr == 'br':
                self.parse_br(val)
    
    def print(self,depth):
        s = ''
        for fun_blk in self.Functions:
            s += fun_blk.print(0) 
        return s


class Parser:
    def __init__(self, r2, script, scriptName, sectionList = []):
        self.scriptName = scriptName
        #print(self.scriptName)
        self.main = SubScript(r2, script, sectionList)
        self.main.Parse()

    
    def Output(self):
        return self.main.print(0)
# WebAdpyser

__WebAdvisor__, [according to Ellucian](http://www.ellucian.com/Software/Colleague-WebAdvisor/),

> [P]resents real-time information such as community news, services, e-commerce
> capabilities, and e-learning offerings—all from one central and secure
> location.

It is terrible. The less anyone has to interact with it, the better. To that
end, __WebAdpyser is a class/script that can currently scrape section
information from WebAdvisor__ instances, and has a __unix-like interface__.

By default, it uses [OASIS](https://oasis.oglethorpe.edu), but other sites that work can
be added via [wa.ini](./wa.ini).

A full listing of options can be found with the --help flag, but here are some
(trimmed) examples:

````
rwb@debian-p:~/python/WebAdpyser$ ./wa.py
usage: wa.py [-h] [-g N] [-f] [-t] [-m] [-s] [-c] [-k] [-v] [-r TERM] [-u url]
             sec [sec ...]
wa.py: error: the following arguments are required: sec

$ ./wa.py MAT -st # Section info and title of all upcoming math classes.
MAT-111-001 Statistics 
MAT-111-002 Statistics 
MAT-120-002 Introduction to Functions 
MAT-120-003 Introduction to Functions 
MAT-121-001 Applied Calculus 
MAT-121-201 Applied Calculus 
MAT-131-001 Calculus I 
MAT-131-002 Calculus I 
MAT-233-001 Calculus III 
MAT-241-001 Proof and Logic 
MAT-471-001 Abstract Algebra 

$ ./wa.py MAT -st -g 200 # Same, but only those >= MAT-200.
MAT-233-001 Calculus III 
MAT-241-001 Proof and Logic 
MAT-471-001 Abstract Algebra 

$ ./wa.py MAT-241 -sftv # Tell me more about MAT-241.
MAT-241-001 Proof and Logic P. Tiu 
This course serves as a general introduction to advanced mathematics.
As such, it will consider various methods of proof communicated
through good mathematical communication (both written and oral).
Topics are drawn from logic, set theory, functions, relations,
combinatorics, graph theory, and Boolean algebra. Offered every
fall semester.  Prerequisite: MAT 132 with a grade of "C-" or higher.

$ ./wa.py MAT-241 -sftmc # Where does it meet? Is it full?
MAT-241-001 Proof and Logic P. Tiu 08/25/2015-12/17/2015 Lecture Tuesday, Thursday 09:45AM - 11:15AM, Robinson Hall, Room 116 15 / 25 

$ ./wa.py MAT -st --term SP16R | sort -r # Show me math classes next term, more advanced first.
MAT-496-001 Senior Seminar in Math 
MAT-490-001 AST: Mathematical Biology 
MAT-236-001 Differential Equations 
MAT-234-001 Calculus IV 
MAT-132-002 Calculus II 
MAT-132-001 Calculus II 
MAT-130-003 Advanced Functions 
MAT-130-002 Advanced Functions 
MAT-130-001 Advanced Functions 
MAT-121-002 Applied Calculus 
MAT-121-001 Applied Calculus 
MAT-120-002 Introduction to Functions 
MAT-120-001 Introduction to Functions 
MAT-111-101 Statistics 
MAT-111-002 Statistics 
MAT-111-001 Statistics 
````
